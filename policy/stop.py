"""The stop button's state, in logs/stops.jsonl (checks/FORMATS.md, section 13.5).

    requested   bin/stop <run_id>, when a person presses it
    effective   the hook's first refusal of the stopped run's calls, or a wait for a person
                that the stop withdraws: the stop has taken effect
    lifted      a resume (python run.py --resume <run_id>) lifts the stop

A run is stopped from a `requested` line until a later `lifted` line. The hook reads
this before every call, so the stop is outside the model: nothing the model says or
does can make a stopped run's call go through.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from harness import ROOT
from harness.clock import now

STOPS = ROOT / "logs" / "stops.jsonl"
_lock = threading.Lock()


def _events(run_id: str, path: Path = STOPS) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("run_id") == run_id:
            out.append(row)
    return out


def _write(run_id: str, event: str, path: Path = STOPS, **fields) -> dict:
    line = {"run_id": run_id, "event": event, "at": now(), **fields}
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as fh:
            fh.write(json.dumps(line) + "\n")
    return line


def request(run_id: str, path: Path = STOPS) -> dict:
    return _write(run_id, "requested", path)


def is_stopped(run_id: str, path: Path = STOPS) -> bool:
    """True from a `requested` line until a later `lifted` one."""
    last = next((e["event"] for e in reversed(_events(run_id, path)) if e.get("event") in ("requested", "lifted")),
                None)
    return last == "requested"


def take_effect(run_id: str, action: str, path: Path = STOPS) -> None:
    """Write `effective` once per stop: at the first call refused, or wait withdrawn, after it."""
    with _lock:
        events = _events(run_id, path)
    since = [e["event"] for e in events[max((i for i, e in enumerate(events) if e.get("event") == "requested"),
                                            default=0):]]
    if "requested" in since and "effective" not in since:
        _write(run_id, "effective", path, action=action)


def lift(run_id: str, path: Path = STOPS) -> bool:
    """A resume lifts the stop; True when there was one to lift."""
    if not is_stopped(run_id, path):
        return False
    _write(run_id, "lifted", path)
    return True
