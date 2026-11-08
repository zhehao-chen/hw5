"""The pre-call hook: RepoMind's autonomy policy, enforced outside the context window.

The registry (tools/__init__.py) runs this hook before every tool call. The hook places
the call in an action class from its arguments and the facts the harness computed
(harness/facts.py), looks the class up in policy/autonomy.yaml, and then:

  0. a stop              refused when bin/stop stopped the run (policy/stop.py), before
                         anything else; a stop also withdraws a request waiting for a person
  1. prohibited         refused, whoever the reviewer is (approve-all included)
  2. a user's boundary   refused when a path the call touches matches a rule in
                         policy/rules.jsonl (policy/rules.py)
  3. the disclosure      refused when a post_comment's body lacks the disclosure line
                         (policy/disclosure.py), before any reviewer is asked
  4. requires_approval   asks the reviewer and waits; a decline or no answer refuses
  5. independent         allowed

A refused call never runs; the model gets an error result, and the refusal is logged
to logs/hook.jsonl. Every decision the reviewer was asked for is logged to
logs/approvals.jsonl. The model never sees the policy file.

`classify` and `place` are pure functions of (action, facts), so bin/replay_policy
places the recorded day with this same code.
"""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

import yaml

from harness import ROOT
from harness.clock import now
from harness.formats import COLUMNS, FILL
from harness.tracker import PROTECTED
from policy import stop
from policy.disclosure import carries

POLICY = ROOT / "policy" / "autonomy.yaml"
LOGS = ROOT / "logs"
HUMAN_ACTIVE_MINUTES = 60         # a person who spoke within the hour is still on the thread
APPROVAL_TIMEOUT_S = 1800         # how long a gated call waits for a person; then it is refused
STOPPED = "a person stopped this run (bin/stop). No further call will be made until it is resumed."
NO_ANSWER = "no reviewer answered in time, so this call was not made. No answer is never a yes."
_lock = threading.Lock()


# -- the policy file ---------------------------------------------------------------------------------
@lru_cache(maxsize=None)
def load_policy(path: str = str(POLICY)) -> dict[str, str]:
    """{action_class: column}. Each class sits in exactly one column."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    placed: dict[str, str] = {}
    for column in COLUMNS:
        for klass in data.get(column) or []:
            if klass in placed:
                raise ValueError(f"policy/autonomy.yaml places {klass} in both {placed[klass]} and {column}")
            placed[str(klass)] = column
    return placed


# -- placing one call ----------------------------------------------------------------------------------
def classify(action: str, facts: dict) -> str:
    """The call's action class, from its facts alone. Never from the model's words."""
    f = facts or {}
    if action == "post_comment":
        minutes = f.get("minutes_since_human_comment")
        if minutes is not None and minutes <= HUMAN_ACTIVE_MINUTES:
            return "post_comment/human_active"          # stricter wins: a person is on the thread now
        if f.get("issue_opened_by_agent") is True:
            return "post_comment/agent_opened"
        return "post_comment/human_quiet"               # a person's issue, or one whose opener is unknown
    if action == "open_pr":
        if f.get("branch_protected") or f.get("base") in PROTECTED:
            return "open_pr/into_protected"
        return "open_pr/into_develop"
    if action == "push_commit":
        if f.get("branch_protected"):
            return "push_commit/protected"
        if f.get("branch") and f.get("target_created_by_agent") is True:
            return "push_commit/own_branch"
        return "push_commit/other_branch"
    if action == "close_issue":
        return "close_issue/agent_opened" if f.get("issue_opened_by_agent") is True else "close_issue/human_opened"
    return action


def place(action: str, facts: dict, policy: dict[str, str] | None = None) -> tuple[str, str]:
    """(action_class, column). A class the policy does not name is prohibited: fail closed."""
    policy = policy if policy is not None else load_policy()
    klass = classify(action, facts)
    column = policy.get(klass) or policy.get(action) or "prohibited"
    return klass, column


# -- the logs ------------------------------------------------------------------------------------------
def _append(name: str, line: dict) -> None:
    with _lock:
        LOGS.mkdir(parents=True, exist_ok=True)
        with (LOGS / name).open("a") as fh:
            fh.write(json.dumps(line, default=str) + "\n")


def log_refusal(run_id, action, klass, column, reason, args, detail: str | None = None) -> None:
    line = {"at": now(), "run_id": run_id, "action": action, "action_class": klass, "column": column,
            "reason": reason, "args": args}
    if detail:
        line["detail"] = detail
    _append("hook.jsonl", line)


def log_decision(run_id, action, klass, facts, kind, answer, mode, reviewer) -> None:
    _append("approvals.jsonl", {
        "at": now(), "run_id": run_id, "action": action, "action_class": klass, "facts": facts, "kind": kind,
        "decision": answer["decision"] if answer else "none",
        "seconds": answer["seconds"] if answer else None,
        "reviewer": answer["reviewer"] if answer else reviewer,
        "mode": answer["mode"] if answer else mode})


# -- the hook ------------------------------------------------------------------------------------------
class PolicyHook:
    """hook(name, args) -> None to allow, or a reason to refuse. Registered in tools/__init__.py."""

    __name__ = "policy_hook"

    def __init__(self, ctx):
        self.ctx = ctx                # the registry's RunContext: run_id, tracker, issue

    def __call__(self, name: str, args: dict) -> str | None:
        from harness.roles import action_of
        rc = self.ctx
        action, klass, column = action_of(name), None, None
        try:
            if action is None:
                log_refusal(rc.run_id, name, None, None, "unknown_action", args)
                return "this tool plays no action the policy knows, so it is refused"

            if stop.is_stopped(rc.run_id):          # first: a person pressed bin/stop
                stop.take_effect(rc.run_id, action)
                log_refusal(rc.run_id, action, None, None, "stopped", args)
                return STOPPED

            if FILL in json.dumps(args, default=str):   # a plan's template, never filled: never sent anywhere
                log_refusal(rc.run_id, action, None, None, "unfilled", args)
                return "an argument still holds the plan's $fill placeholder; fill it before calling."

            facts = rc.tracker.facts(rc.run_id, action, args, rc.issue)
            klass, column = place(action, facts)

            if column == "prohibited":
                log_refusal(rc.run_id, action, klass, column, "prohibited", args)
                return f"RepoMind's policy never allows {klass}. Do not retry it; continue without it."

            rule = _boundary(rc.run_id, facts.get("paths") or [])
            if rule is not None:
                log_refusal(rc.run_id, action, klass, None, "boundary", args,
                            detail=f"{facts.get('paths')} crosses {rule['path']}")
                return (f"the user set a boundary for this run ({rule['message'].strip()}); this call crosses it. "
                        "Do not retry it.")

            if action == "post_comment" and not carries(_arg(args, "comment", "body")):
                log_refusal(rc.run_id, action, klass, None, "disclosure", args)
                return "a comment must say that an automated agent wrote it; this one does not, so it was not posted."

            if column == "requires_approval":
                return self._ask(action, klass, column, args, facts)
            return None
        except Exception as exc:  # fail closed, and say so in the log
            log_refusal(rc.run_id, action or name, klass, column, "error", args, detail=f"{type(exc).__name__}: {exc}")
            raise

    def _ask(self, action, klass, column, args, facts) -> str | None:
        from harness.reviewer import Reviewer
        rc = self.ctx
        reviewer = Reviewer.from_env()
        request = {"run_id": rc.run_id, "action": action, "action_class": klass, "args": args, "facts": facts,
                   "kind": "approval", "issue": facts.get("issue")}
        answer = reviewer.ask(request, timeout_s=APPROVAL_TIMEOUT_S, until=lambda: stop.is_stopped(rc.run_id))
        log_decision(rc.run_id, action, klass, facts, "approval", answer, reviewer.mode, reviewer.kind)
        if answer is None and stop.is_stopped(rc.run_id):    # the stop withdrew the request
            stop.take_effect(rc.run_id, action)
            log_refusal(rc.run_id, action, klass, column, "stopped", args)
            return STOPPED
        if answer is None:
            log_refusal(rc.run_id, action, klass, column, "no_answer", args)
            return NO_ANSWER
        if answer["decision"] != "approve":
            log_refusal(rc.run_id, action, klass, column, "declined", args)
            return "a reviewer declined this call. Do not retry it."
        return None


def _arg(args: dict, role: str, name: str):
    from harness.roles import arg
    return (args or {}).get(arg(role, name))


def _boundary(run_id: str, paths: list[str]) -> dict | None:
    from policy.rules import crossing
    return crossing(run_id, paths)
