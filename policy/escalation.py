"""Escalation: the run stops, at runtime, to ask a person (Lecture 5, slides 34 to 38).

The trigger is one of four signals named in advance, each set by the harness, never by
the model, and checked before an action that cannot be undone (slide 37):

    failed_verification      this run's own run_tests failed, and the next step is a push
    memory_contradiction     the draft disagrees with an active record in the memory store
    uninterpretable_result   a tool result the harness cannot interpret (a write it cannot
                             confirm, a test result it cannot parse)
    blocked_three_times      the hook refused the same plan step three times

Never "low confidence": the model's report of its own doubt is not a signal.

What escalate() does, in order:
  1. writes the packet, escalations/<run_id>.json: attempted, why_stopped, needs_from_human;
  2. the caller has already saved a checkpoint; this writes the trace's escalation line;
  3. checks the day's cap; a capped escalation is logged and holds its run unasked;
  4. asks the same reviewer the gated calls use, and waits up to ESCALATION_TIMEOUT_S.
     No answer is never a yes: the caller ends the run held.

Returns "approve", "deny", "held" (no answer, or the cap), or "stopped" (bin/stop
withdrew the question).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from harness import ROOT
from harness.clock import now, parse
from harness.notify import notify
from policy import stop
from policy.hook import log_decision, place

SIGNALS = ("failed_verification", "memory_contradiction", "uninterpretable_result", "blocked_three_times")
PACKETS = ROOT / "escalations"
LOG = ROOT / "logs" / "escalations.jsonl"
ESCALATION_TIMEOUT_S = 1800
# The reviewer's budget is 600 seconds a day, and the replay already spends it on 14
# prompts. An escalation needs more reading than an approval (about two minutes: the
# packet, the test failure, the change), so at most three a day reach any one reviewer.
ESCALATIONS_PER_DAY = 3
_lock = threading.Lock()


def _log(line: dict) -> None:
    with _lock:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as fh:
            fh.write(json.dumps({"at": now(), **line}, default=str) + "\n")


def asked_today(mode: str) -> int:
    """Escalations already put to this reviewer mode on this UTC day."""
    if not LOG.exists():
        return 0
    today = datetime.now(timezone.utc).date()
    count = 0
    for raw in LOG.read_text().splitlines():
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "asked" and row.get("mode") == mode and parse(row["at"]).date() == today:
            count += 1
    return count


def escalate(ctx, *, signal: str, step, action: str, args: dict, attempted: str, why_stopped: str,
             needs_from_human: str, evidence: dict | None = None) -> str:
    from harness.reviewer import Reviewer

    if signal not in SIGNALS:
        raise ValueError(f"an escalation fires on a named signal, one of {SIGNALS}, not {signal!r}")
    run_id = ctx.run_id
    packet = {"attempted": attempted, "why_stopped": why_stopped, "needs_from_human": needs_from_human,
              "signal": signal, "at": now(), "run_id": run_id, "issue": ctx.issue_number, "step": step,
              "action": action, "evidence": evidence or {},
              "resume": f"python run.py --resume {run_id}"}
    PACKETS.mkdir(parents=True, exist_ok=True)
    path = PACKETS / f"{run_id}.json"
    path.write_text(json.dumps(packet, indent=2, default=str) + "\n")
    ctx.trace.event("escalation", signal=signal, packet=str(path.relative_to(ROOT)), step=step)

    reviewer = Reviewer.from_env()
    if asked_today(reviewer.mode) >= ESCALATIONS_PER_DAY:
        _log({"event": "capped", "run_id": run_id, "signal": signal, "mode": reviewer.mode,
              "cap": ESCALATIONS_PER_DAY})
        notify("escalation_capped", run_id, f"escalation cap ({ESCALATIONS_PER_DAY} a day) reached: run {run_id} "
               f"holds, unasked; its packet is {path.relative_to(ROOT)}")
        return "held"

    facts = ctx.tracker.facts(run_id, action, args, ctx.issue_number)
    klass, _ = place(action, facts)
    _log({"event": "asked", "run_id": run_id, "signal": signal, "mode": reviewer.mode})
    notify("escalation", run_id, f"RepoMind stopped to ask on issue {ctx.issue_number}: {why_stopped}")
    request = {"run_id": run_id, "action": action, "action_class": klass, "args": args, "facts": facts,
               "kind": "escalation", "packet": packet, "issue": ctx.issue_number}
    answer = reviewer.ask(request, timeout_s=ESCALATION_TIMEOUT_S, until=lambda: stop.is_stopped(run_id))
    log_decision(run_id, action, klass, facts, "escalation", answer, reviewer.mode, reviewer.kind)
    if answer is None and stop.is_stopped(run_id):
        stop.take_effect(run_id, action)
        return "stopped"
    if answer is None:
        return "held"
    return answer["decision"]
