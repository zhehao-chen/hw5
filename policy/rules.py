"""Boundaries a user states, promoted to rules the hook reads (Lecture 5, slide 17).

A boundary arrives through the inbox as a message, `BOUNDARY: deny path=<glob>`. The
harness parses it here, never the model, and appends it to policy/rules.jsonl. The hook
reads that file before every call, so the rule outlives any compaction of the history.
A rule holds for the run it was stated to, and for that run's resume (same run_id).
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from harness import ROOT
from harness.clock import now
from harness.formats import BOUNDARY, normalize_path

RULES = ROOT / "policy" / "rules.jsonl"
_lock = threading.Lock()


def parse(text: str) -> str | None:
    """The glob a boundary message denies, or None when the message is not a boundary."""
    match = BOUNDARY.match(str(text or ""))
    return match.group(1) if match else None


def add(run_id: str, glob: str, message: str, stated_at: str | None = None, path: Path = RULES) -> dict:
    rule = {"run_id": run_id, "effect": "deny", "path": glob, "stated_at": stated_at or now(), "message": message}
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(json.dumps(rule) + "\n")
    return rule


def for_run(run_id: str, path: Path = RULES) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            rule = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rule.get("run_id") == run_id and rule.get("effect") == "deny":
            out.append(rule)
    return out


def glob_regex(glob: str) -> re.Pattern:
    """`**` matches any number of directories, `*` any characters within one, `?` one."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(f"^{out}$")


def crossing(run_id: str, paths: list[str], path: Path = RULES) -> dict | None:
    """The first rule of this run that one of the call's paths crosses, or None."""
    rules = for_run(run_id, path)
    if not rules or not paths:
        return None
    for p in paths:
        clean = normalize_path(str(p))
        if not clean or clean == "none":
            continue
        for rule in rules:
            if glob_regex(rule["path"]).match(clean):
                return rule
    return None
