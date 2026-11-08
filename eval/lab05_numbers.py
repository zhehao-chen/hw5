"""Assignment 5's measured numbers, from the logs, the way make check-05 recomputes them.

    python eval/lab05_numbers.py            # print them
    python eval/lab05_numbers.py --write    # also write diagnostics and stop into reports/LAB_05.json

Only runs of a real model in this lab count (runs/<run_id>.jsonl's run_start: lab "05",
a backend that is not scripted).

diagnostics: over the human approvals in logs/approvals.jsonl (reviewer human, kind
approval, decision approve or deny): the count, the approval rate, the rate on the classes
the ranking marks undo none and blast wide, and the median seconds per class.
stop: every stop in logs/stops.jsonl that took effect (requested, then effective), its
latency in seconds, the median and the largest.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import LAB  # noqa: E402
from harness.clock import seconds_between  # noqa: E402
from harness.runner import is_free  # noqa: E402

REPORT = ROOT / "reports" / "LAB_05.json"


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def real_runs() -> set[str]:
    out = set()
    for path in (ROOT / "runs").glob("*.jsonl"):
        if path.name.startswith("_") or path.name.count(".") > 1:
            continue
        try:
            start = json.loads(path.open().readline())
        except (json.JSONDecodeError, OSError):
            continue
        if start.get("type") == "run_start" and str(start.get("lab")) == str(LAB) \
                and not is_free(str(start.get("backend") or "")):
            out.add(start.get("run_id") or path.stem)
    return out


def diagnostics(report: dict, real: set[str]) -> dict:
    decided = [a for a in jsonl(ROOT / "logs" / "approvals.jsonl")
               if a.get("reviewer") == "human" and (a.get("kind") or "approval") == "approval"
               and a.get("run_id") in real and a.get("decision") in ("approve", "deny")]
    wide_classes = sorted({r["action_class"] for r in report.get("ranking") or []
                           if r.get("undo") == "none" and r.get("blast") == "wide"})
    wide = [a for a in decided if a.get("action_class") in wide_classes]
    rate = lambda xs: round(sum(a["decision"] == "approve" for a in xs) / len(xs), 2) if xs else None
    by_class: dict[str, list[float]] = {}
    for a in decided:
        if isinstance(a.get("seconds"), (int, float)):
            by_class.setdefault(a["action_class"], []).append(float(a["seconds"]))
    counts = {k: {"decisions": sum(a["action_class"] == k for a in decided),
                  "approved": sum(a["action_class"] == k and a["decision"] == "approve" for a in decided)}
              for k in by_class}
    return {"decisions": len(decided), "approval_rate_all": rate(decided), "approval_rate_irreversible_wide": rate(wide),
            "irreversible_wide_classes": wide_classes,
            "median_seconds_by_class": {k: round(statistics.median(v), 1) for k, v in sorted(by_class.items())},
            "_by_class": counts}


def stops(real: set[str]) -> dict:
    events: dict[str, dict] = {}
    for line in jsonl(ROOT / "logs" / "stops.jsonl"):
        rid = line.get("run_id")
        if rid not in real:
            continue
        ev = events.setdefault(rid, {})
        if line.get("event") == "requested" and "effective" not in ev:
            ev["requested"] = line["at"]
        elif line.get("event") == "effective" and "effective" not in ev and "requested" in ev:
            ev["effective"] = line["at"]
    took = {rid: ev for rid, ev in events.items() if "requested" in ev and "effective" in ev}
    latencies = [seconds_between(ev["requested"], ev["effective"]) for ev in took.values()]
    return {"run_ids": list(took), "latencies_s": latencies,
            "p50_s": round(statistics.median(latencies), 3) if latencies else None,
            "max_s": round(max(latencies), 3) if latencies else None}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--write", action="store_true", help="write diagnostics and stop into reports/LAB_05.json")
    a = p.parse_args(argv)
    report = json.loads(REPORT.read_text())
    real = real_runs()
    diag, stop = diagnostics(report, real), stops(real)
    print(f"runs of your model in this lab: {len(real)}")
    print("diagnostics:", json.dumps(diag, indent=1))
    print("stop:", json.dumps(stop, indent=1))
    if a.write:
        diag.pop("_by_class")
        report["diagnostics"] = diag
        report["stop"] = {**report.get("stop", {}), **stop}
        REPORT.write_text(json.dumps(report, indent=2) + "\n")
        print(f"written to {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
