"""Enforce independent line and branch coverage thresholds."""

import json
import sys
from pathlib import Path
from typing import TypedDict, cast

THRESHOLD = 95.0
COVERAGE_FILE = Path("coverage.json")


class CoverageTotals(TypedDict):
    """Subset of Coverage.py's JSON totals consumed by this gate."""

    num_statements: int
    covered_lines: int
    num_branches: int
    covered_branches: int


class CoverageReport(TypedDict):
    """Coverage.py JSON root consumed by this gate."""

    totals: CoverageTotals


def _percentage(covered: int, total: int) -> float:
    """Return a percentage, treating an empty category as complete."""
    return 100.0 if total == 0 else covered / total * 100


def main() -> int:
    """Validate line and branch coverage independently."""
    report = cast(
        "CoverageReport",
        json.loads(COVERAGE_FILE.read_text(encoding="utf-8")),
    )
    totals = report["totals"]
    line_coverage = _percentage(totals["covered_lines"], totals["num_statements"])
    branch_coverage = _percentage(totals["covered_branches"], totals["num_branches"])
    print(f"Line coverage: {line_coverage:.2f}%")
    print(f"Branch coverage: {branch_coverage:.2f}%")
    if line_coverage < THRESHOLD or branch_coverage < THRESHOLD:
        print(f"Both values must be at least {THRESHOLD:.0f}%.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
