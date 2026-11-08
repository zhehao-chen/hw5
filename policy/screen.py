"""The approval screen bin/review shows (Lecture 5, slides 19, 27 and 30).

render(request) -> str. It shows information, never a recommendation:

  1. what is asked: the action and its class (or, for an escalation, the packet);
  2. the dry run: the write exactly as it would be applied (a comment's text as it will
     appear; a pull request's branch, base, title and body; a push's branch, message and
     files);
  3. facts the harness computed, never the model's claims: who opened the issue, when a
     person last spoke, whether RepoMind made the target or found it, branch protection,
     the files touched, this run's own test result, and what this run already wrote;
  4. the thread, as people wrote it: the issue and its discussion, newest last.

The model's rationale is not shown at all: the system under review does not write the
case for its own approval (OWASP ASI09).
"""

from __future__ import annotations

import json
import re
import textwrap

from harness import ROOT
from harness.formats import SENTINEL

WIDTH = 72
BODY_LINES = 14        # of the issue's body
COMMENT_LINES = 8      # of each discussion entry
DISCUSSION_SHOWN = 4   # the newest entries


def _arg(args: dict, role: str, name: str):
    from harness.roles import arg
    try:
        return (args or {}).get(arg(role, name))
    except (KeyError, OSError, ValueError):
        return (args or {}).get(name)


def _wrap(text: str, indent: str = "  ", limit: int | None = None) -> list[str]:
    out = []
    for raw in str(text or "").splitlines() or [""]:
        out += textwrap.wrap(raw, WIDTH - len(indent), replace_whitespace=False) or [""]
    if limit is not None and len(out) > limit:
        out = out[:limit] + [f"… ({len(out) - limit} more lines)"]
    return [indent + line for line in out]


def _prose(text: str) -> str:
    """People's text reflowed: lines within a paragraph joined, the fixture's sentinel dropped.
    The words are unchanged; only the fixture's hard line breaks go."""
    text = SENTINEL.sub("", str(text or "")).strip()
    paragraphs = re.split(r"\n\s*\n", text)
    return "\n\n".join(" ".join(p.split("\n")) if not p.lstrip().startswith(("-", "*", "|", "```", "    "))
                       else p for p in paragraphs)


def _unfilled(value) -> str:
    return "(not written yet)" if str(value or "").startswith("$fill") else str(value)


def _box(text: str) -> list[str]:
    """The text exactly as it will appear, line for line, in a frame."""
    lines = ["  ┌" + "─" * (WIDTH - 4)]
    for raw in str(text or "").splitlines() or [""]:
        for piece in textwrap.wrap(raw, WIDTH - 6) or [""]:
            lines.append("  │ " + piece)
    lines.append("  └" + "─" * (WIDTH - 4))
    return lines


def _yes(value, yes: str, no: str, unknown: str = "unknown") -> str:
    return yes if value is True else no if value is False else unknown


# -- the facts this run left behind --------------------------------------------------------------------
def _calls(run_id: str) -> list[dict]:
    path = ROOT / "runs" / f"{run_id}.calls.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _tests(run_id: str) -> str:
    from harness.roles import tool_for
    try:
        name = tool_for("run_tests")
    except (KeyError, OSError, ValueError):
        name = "code_run_tests"
    runs = [c for c in _calls(run_id) if c.get("tool") == name]
    if not runs:
        return "not run in this run"
    last = runs[-1]
    if last.get("is_error"):
        return f"the test call failed: {str(last.get('result'))[:80]}"
    try:
        data = json.loads(last.get("result") or "")
    except ValueError:
        return f"unreadable result: {str(last.get('result'))[:80]}"
    ref = data.get("ref")
    if data.get("passed") is True:
        return f"PASSED on {ref} ({data.get('tests')} tests)"
    return f"FAILED on {ref}: {', '.join(data.get('failed') or []) or '?'}"


def _written(run_id: str, asked_at: str | None = None) -> list[str]:
    """What the remote took from this run before the request was asked."""
    try:
        from harness.clock import parse
        from harness.tracker import Tracker
        log = Tracker().log(run_id)
        if asked_at:
            log = [w for w in log if parse(w["at"]) <= parse(asked_at)]
    except Exception as exc:  # the screen still shows, without this line
        return [f"(the remote could not be read: {type(exc).__name__})"]
    done = [f"{w['action']} → {w['target']} ({w['outcome']})" for w in log]
    return done or ["nothing yet"]


def _issue(number) -> dict | None:
    if number is None:
        return None
    try:
        from harness.tracker import Tracker
        return Tracker().issue(int(number))
    except Exception:
        return None


# -- the sections ------------------------------------------------------------------------------------------
def _header(request: dict) -> list[str]:
    from policy.hook import load_policy
    klass = request.get("action_class") or request.get("action")
    column = load_policy().get(klass, "?")
    if request.get("kind") == "escalation":
        return [f"ESCALATION · the run stopped to ask, before {request.get('action')}  [{klass}]"]
    return [f"APPROVAL · {klass}  (policy column: {column})"]


def _packet(request: dict) -> list[str]:
    p = request.get("packet") or {}
    lines = ["", "WHY THE RUN STOPPED  (the harness's signal, not the model's words)",
             f"  signal:            {p.get('signal')}"]
    for key in ("attempted", "why_stopped", "needs_from_human"):
        lines += [f"  {key}:"] + _wrap(p.get(key), "      ")
    return lines


def _dry_run(request: dict) -> list[str]:
    action, args = request.get("action"), request.get("args") or {}
    lines = ["", "DRY RUN · exactly what would be written"]
    if action == "post_comment":
        number = _arg(args, "comment", "number")
        lines.append(f"  a public comment on {number}, visible to everyone on the thread:")
        lines += _box(_arg(args, "comment", "body"))
    elif action == "open_pr":
        lines += [f"  a public draft pull request, opened now:",
                  f"  branch: {_arg(args, 'open_pr', 'branch')}   →   base: {(request.get('facts') or {}).get('base')}",
                  f"  for:    {_arg(args, 'open_pr', 'number')}",
                  f"  title:  {_arg(args, 'open_pr', 'title')}", "  body:"]
        lines += _box(_arg(args, "open_pr", "body"))
    elif action == "push_commit":
        files = _arg(args, "push_commit", "files")
        lines += [f"  a commit pushed to {_arg(args, 'push_commit', 'branch')} (a push cannot be undone):",
                  f"  message: {_unfilled(_arg(args, 'push_commit', 'message'))}",
                  f"  files:   {', '.join(files) if isinstance(files, list) else _unfilled(files)}"]
        if request.get("kind") == "escalation":
            lines.append("  (asked before the model writes the commit: if you approve, the push itself still "
                         "comes to you for approval, with its message and files)")
    elif action == "apply_label":
        lines.append(f"  label {_arg(args, 'apply_label', 'label')!r} added to {_arg(args, 'apply_label', 'number')}")
    elif action == "close_issue":
        lines.append(f"  {_arg(args, 'close_issue', 'number')} closed, reason: {_arg(args, 'close_issue', 'reason')}")
    elif action == "merge_pr":
        lines.append(f"  {_arg(args, 'merge_pr', 'pr')} merged")
    else:
        lines += _wrap(json.dumps(args, indent=1, default=str))
    return lines


def _facts(request: dict, issue: dict | None) -> list[str]:
    f = request.get("facts") or {}
    run_id = request.get("run_id")
    minutes = f.get("minutes_since_human_comment")
    author = (issue or {}).get("author")
    lines = ["", "FACTS · computed by the harness, not asserted by the model",
             f"  issue:                 #{f.get('issue')}"
             + (f"  “{issue.get('title')}”" if issue and issue.get("title") else ""),
             f"  opened by:             "
             + _yes(f.get("issue_opened_by_agent"), "RepoMind (the agent)", f"a person ({author or '?'})"),
             f"  last human comment:    "
             + ("none on this thread" if minutes is None else f"{minutes:g} minutes ago"),
             f"  target:                "
             + _yes(f.get("target_created_by_agent"), "created by RepoMind", "found: RepoMind did not create it",
                    "n/a")]
    if f.get("branch") or f.get("base"):
        where = f"{f.get('branch')} → {f.get('base')}" if f.get("base") else f"{f.get('branch')}"
        lines.append(f"  branch:                {where}   protected: "
                     + _yes(f.get("branch_protected"), "YES", "no", "n/a"))
    if f.get("paths"):
        lines.append(f"  files touched:         {', '.join(f['paths'])}")
    lines.append(f"  this run's tests:      {_tests(run_id)}")
    lines.append("  this run has written:  " + "; ".join(_written(run_id, request.get("asked_at"))))
    return lines


def _thread(issue: dict | None) -> list[str]:
    if issue is None:
        return ["", "THE THREAD · (the issue could not be read)"]
    lines = ["", "THE THREAD · as people wrote it",
             f"  #{issue.get('number')} {issue.get('title')}  — opened by {issue.get('author')} on {issue.get('opened')}"]
    lines += _wrap(_prose(issue.get("body")), "  │ ", BODY_LINES)
    discussion = issue.get("discussion") or []
    if not discussion:
        lines.append("  (no discussion)")
        return lines
    hidden = len(discussion) - DISCUSSION_SHOWN
    if hidden > 0:
        lines.append(f"  … {hidden} earlier comment(s) not shown")
    shown = discussion[-DISCUSSION_SHOWN:]
    for i, entry in enumerate(shown):
        role = f" ({entry['role']})" if entry.get("role") else ""
        latest = "   ← latest" if i == len(shown) - 1 else ""
        lines.append(f"  ▸ {entry.get('author')}{role} · {entry.get('date')}{latest}")
        lines += _wrap(_prose(entry.get("body")), "    ", COMMENT_LINES)
    return lines


def render(request: dict) -> str:
    facts = request.get("facts") or {}
    issue = _issue(facts.get("issue") or request.get("issue"))
    lines = _header(request)
    if request.get("kind") == "escalation":
        lines += _packet(request)
    lines += _dry_run(request)
    lines += _facts(request, issue)
    lines += _thread(issue)
    lines += ["", "No rationale from the model is shown: the agent does not argue its own case."]
    return "\n".join(lines)
