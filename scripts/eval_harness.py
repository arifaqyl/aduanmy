#!/usr/bin/env python3
"""Eval harness for the Threads rider-signal gate.

MANUS_PROMPT.md is explicit: don't loosen transport_rider_signal_worthwhile()
without labelled eval cases. This is that harness.

Usage:
  python scripts/eval_harness.py                       # run against the seed set
  python scripts/eval_harness.py --cases path/to.json   # run against a different set
  python scripts/eval_harness.py --save-baseline        # snapshot current results as the baseline
  python scripts/eval_harness.py --fail-on-regression   # exit 1 if any case that
                                                         # previously passed now fails

Case file format: JSON list of {"text": str, "entity_hint": str (optional),
"expected": bool, "note": str (optional)}.

Extending the eval set: when a false positive/negative from production shows
up (see docs/PRODUCTION_AUDIT_*.md or a QA sample), add it here with the
correct `expected` label *before* touching the gate. That's what keeps this
useful — most of the current seed cases came from exactly that kind of
regression report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.pipeline.extract import transport_rider_signal_worthwhile  # noqa: E402

DEFAULT_CASES = REPO / "tests" / "eval" / "rider_signal_cases.json"
BASELINE_PATH = REPO / "tests" / "eval" / "rider_signal_baseline.json"


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        actual = transport_rider_signal_worthwhile(case["text"], case.get("entity_hint", ""))
        results.append({**case, "actual": actual, "pass": actual == case["expected"]})
    return results


def summarize(results: list[dict]) -> dict:
    total = len(results)
    passed = sum(r["pass"] for r in results)
    tp = sum(1 for r in results if r["expected"] and r["actual"])
    fp = sum(1 for r in results if not r["expected"] and r["actual"])
    fn = sum(1 for r in results if r["expected"] and not r["actual"])
    tn = sum(1 for r in results if not r["expected"] and not r["actual"])
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    return {
        "total": total,
        "passed": passed,
        "accuracy": passed / total if total else float("nan"),
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--save-baseline", action="store_true")
    parser.add_argument("--fail-on-regression", action="store_true")
    parser.add_argument("--quiet", action="store_true", help="only print the summary line")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    results = run(cases)
    stats = summarize(results)

    failures = [r for r in results if not r["pass"]]
    if not args.quiet:
        for r in failures:
            kind = "false positive" if r["actual"] else "false negative"
            print(f"  FAIL ({kind}): {r['text'][:80]!r} — note: {r.get('note', '')}")

    print(
        f"{stats['passed']}/{stats['total']} passed | "
        f"accuracy {stats['accuracy']:.1%} | precision {stats['precision']:.1%} | "
        f"recall {stats['recall']:.1%} | fp={stats['fp']} fn={stats['fn']}"
    )

    regressed = False
    if args.fail_on_regression and BASELINE_PATH.exists():
        baseline = {r["text"]: r["pass"] for r in json.loads(BASELINE_PATH.read_text(encoding="utf-8"))}
        for r in results:
            if baseline.get(r["text"], True) and not r["pass"]:
                regressed = True
                print(f"  REGRESSION vs baseline: {r['text'][:80]!r}")

    if args.save_baseline:
        BASELINE_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Saved baseline: {BASELINE_PATH}")

    if failures or regressed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
