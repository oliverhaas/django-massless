#!/usr/bin/env python3
"""Compare two benchmark reports produced by run.sh (e.g. django-bolt vs massless).

Usage:
    python compare.py BASELINE.md CANDIDATE.md [--max-regression PCT]

BASELINE is typically django-bolt; CANDIDATE is massless. The gate enforces the
design goal: massless must match or beat django-bolt on framework-bound (non-DB)
endpoints (design sections 2 and 9). DB-bound cases are reported but not gated:
they converge to the Django ORM ceiling by design.
"""

from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path

REQS_RE = re.compile(r"Reqs/sec\s+([0-9.]+)")

# Framework-bound core endpoints massless must not regress on versus the baseline.
# Phase 1 ships only framework-bound, no-body, async endpoints. The keys to restore
# as later phases add header access and request-body parsing are:
#   Header Param (/header), Cookie Param (/cookie), JSON Parse/Validate (/bench/parse)
CORE_KEYS = (
    "Root JSON Async (/)",
    "10kb JSON Async (/10k-json)",
    "Path Param int (/items/12345)",
    "Path + Query (/items/12345?q=hello)",
)


def parse(path: Path) -> dict[str, float]:
    entries: dict[str, float] = {}
    current: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("### "):
            current = line[4:].strip()
        match = REQS_RE.search(line)
        if match and current:
            entries[current] = float(match.group(1))
    return entries


def pct_delta(old: float, new: float) -> float:
    return 0.0 if old == 0 else (new - old) / old * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Baseline report (e.g. django-bolt).")
    parser.add_argument("candidate", type=Path, help="Candidate report (e.g. massless).")
    parser.add_argument(
        "--max-regression",
        type=float,
        default=2.0,
        help="Maximum allowed RPS regression (%%) per core endpoint before failing.",
    )
    args = parser.parse_args()

    baseline = parse(args.baseline)
    candidate = parse(args.candidate)

    common = sorted(set(baseline) & set(candidate))
    if not common:
        print("ERROR: no comparable benchmark entries found.", file=sys.stderr)
        return 2

    print(f"{'endpoint':52}{'baseline':>13}{'candidate':>13}{'delta':>9}")
    print("-" * 87)
    for key in common:
        old, new = baseline[key], candidate[key]
        print(f"{key:52}{old:13.1f}{new:13.1f}{pct_delta(old, new):>+8.1f}%")

    missing = [k for k in CORE_KEYS if k not in baseline or k not in candidate]
    if missing:
        print("\nERROR: missing core framework-bound endpoints:", file=sys.stderr)
        for key in missing:
            print(f"  - {key}", file=sys.stderr)
        return 2

    core_deltas = [pct_delta(baseline[k], candidate[k]) for k in CORE_KEYS]
    regressed = [(k, d) for k, d in zip(CORE_KEYS, core_deltas, strict=True) if d < -args.max_regression]

    print(f"\nCore framework-bound endpoints: {len(core_deltas)}")
    print(f"Median delta vs baseline: {statistics.median(core_deltas):+.1f}%")

    if regressed:
        print(f"\nFAIL: {len(regressed)} core endpoint(s) regressed by more than {args.max_regression:.1f}%:")
        for key, delta in sorted(regressed, key=lambda kv: kv[1]):
            print(f"  - {key}: {delta:+.1f}%")
        return 1

    print("\nPASS: massless matches or beats the baseline on all core framework-bound endpoints.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
