#!/usr/bin/env python3
"""Validate combined line and branch coverage from coverage JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_totals(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Coverage file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    totals = payload.get("totals")
    if not isinstance(totals, dict):
        raise ValueError("Coverage JSON missing 'totals' object")
    return totals


def _line_percent(totals: dict) -> float:
    value = totals.get("percent_statements_covered")
    if isinstance(value, (int, float)):
        return float(value)
    covered = totals.get("covered_lines", 0)
    statements = totals.get("num_statements", 0)
    if statements == 0:
        return 100.0
    return (float(covered) / float(statements)) * 100.0


def _branch_percent(totals: dict) -> float:
    value = totals.get("percent_branches_covered")
    if isinstance(value, (int, float)):
        return float(value)
    branches = totals.get("num_branches", 0)
    covered = totals.get("covered_branches", 0)
    if isinstance(branches, int) and branches <= 0:
        return 100.0
    return (float(covered) / float(branches)) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce coverage thresholds")
    parser.add_argument("coverage_json", type=Path)
    parser.add_argument("--line", type=float, required=True)
    parser.add_argument("--branch", type=float, required=True)
    args = parser.parse_args()

    totals = _load_totals(args.coverage_json)
    line_pct = _line_percent(totals)
    branch_pct = _branch_percent(totals)

    failures: list[str] = []
    if line_pct < args.line:
        failures.append(
            f"Line coverage {line_pct:.2f}% is below required {args.line:.2f}%"
        )
    if branch_pct < args.branch:
        failures.append(
            f"Branch coverage {branch_pct:.2f}% is below required {args.branch:.2f}%"
        )

    print(f"Line coverage:   {line_pct:.2f}%")
    print(f"Branch coverage: {branch_pct:.2f}%")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    print("Coverage thresholds satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
