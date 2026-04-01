from __future__ import annotations

import argparse
import sys
from pathlib import Path

from testing.qa.harness import QaHarness, QaHarnessConfig, default_python, print_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the isolated QA harness for my_grc.")
    parser.add_argument(
        "--check",
        action="append",
        choices=["security", "database", "unit", "cli", "workspace"],
        help="Run only the selected check. Repeat to select more than one.",
    )
    parser.add_argument(
        "--python",
        default=default_python(),
        help="Python interpreter to use for subprocess-based checks.",
    )
    parser.add_argument(
        "--keep-run-dir",
        action="store_true",
        help="Keep the temporary isolated runtime directory for debugging.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing check.",
    )
    parser.add_argument(
        "--output-json",
        default=str(Path("testing") / "qa" / "reports" / "latest.json"),
        help="Write the machine-readable report to this path.",
    )
    parser.add_argument(
        "--output-md",
        default=str(Path("testing") / "qa" / "reports" / "latest.md"),
        help="Write the markdown summary to this path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = QaHarnessConfig(
        python_bin=args.python,
        keep_run_dir=args.keep_run_dir,
        fail_fast=args.fail_fast,
        selected_checks=args.check,
        output_json=Path(args.output_json) if args.output_json else None,
        output_md=Path(args.output_md) if args.output_md else None,
    )
    report = QaHarness(config).run()
    print_report(report)
    if config.output_json:
        print(f"JSON report: {config.output_json}")
    if config.output_md:
        print(f"Markdown report: {config.output_md}")
    if report["kept_run_dir"] and report["run_dir"]:
        print(f"Kept isolated run directory: {report['run_dir']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
