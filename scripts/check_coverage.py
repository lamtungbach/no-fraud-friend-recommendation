"""Fail when a covered Sprint 2 package falls below the required threshold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def package_coverage(report: dict, package: str) -> float | None:
    prefix = package.replace("\\", "/").rstrip("/") + "/"
    totals = {"covered_lines": 0, "num_statements": 0}
    for filename, data in report["files"].items():
        normalized = filename.replace("\\", "/")
        if normalized.startswith(prefix) or f"/{prefix}" in normalized:
            summary = data["summary"]
            totals["covered_lines"] += summary["covered_lines"]
            totals["num_statements"] += summary["num_statements"]
    if totals["num_statements"] == 0:
        return None
    return 100 * totals["covered_lines"] / totals["num_statements"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report", type=Path, default=Path("artifacts/sprint2/coverage.json")
    )
    parser.add_argument("--minimum", type=float, default=80)
    parser.add_argument(
        "--packages", nargs="+", default=["src/graph", "src/serving", "src/retrieval"]
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures: list[str] = []
    for package in args.packages:
        coverage = package_coverage(report, package)
        if coverage is None:
            failures.append(f"{package}: no measured statements")
        else:
            print(f"{package}: {coverage:.2f}%")
            if coverage < args.minimum:
                failures.append(f"{package}: {coverage:.2f}% < {args.minimum:.2f}%")
    if failures:
        print("Coverage gate failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
