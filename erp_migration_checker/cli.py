from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .engine import DataError, compare_files
from .reports import json_report, markdown_report, write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="erp-migration-check",
        description="Compare two ERP migration CSV extracts using an explicit JSON mapping.",
    )
    parser.add_argument("--config", required=True, type=Path, help="JSON mapping and reconciliation rules.")
    parser.add_argument("--source", required=True, type=Path, help="Source-system CSV extract.")
    parser.add_argument("--target", required=True, type=Path, help="Target-system CSV extract.")
    parser.add_argument("--json-out", type=Path, help="Write a machine-readable JSON report.")
    parser.add_argument("--markdown-out", type=Path, help="Write a review-friendly Markdown report.")
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="Include raw compared values and aggregate totals in reports; outputs may contain sensitive data.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_paths(args)
        config = load_config(args.config)
        report = compare_files(args.source, args.target, config, include_values=args.show_values)
        if args.json_out:
            write_report(args.json_out, json_report(report, args.show_values), (args.config, args.source, args.target))
        if args.markdown_out:
            write_report(args.markdown_out, markdown_report(report, args.show_values), (args.config, args.source, args.target))
    except (ConfigError, DataError, OSError, ValueError) as exc:
        print(f"Input or report error: {exc}", file=sys.stderr)
        return 2

    error_count = sum(f.severity == "error" for f in report.findings)
    warning_count = sum(f.severity == "warning" for f in report.findings)
    print(
        f"{report.status}: {report.matched_key_count} matched key(s), "
        f"{error_count} error(s), {warning_count} warning(s)."
    )
    for finding in report.findings:
        source_ref = ",".join(f"S{n}" for n in finding.source_rows) or "-"
        target_ref = ",".join(f"T{n}" for n in finding.target_rows) or "-"
        location = f"source={source_ref} target={target_ref}"
        field = f" field={finding.field!r}" if finding.field else ""
        print(f"[{finding.severity.upper()}] {finding.code}:{field} {location} {finding.message}")
    for path in (args.json_out, args.markdown_out):
        if path:
            print(f"Report written: {path}")
    return 1 if error_count else 0


def _validate_paths(args: argparse.Namespace) -> None:
    source = args.source.resolve()
    target = args.target.resolve()
    if source == target:
        raise ValueError("Source and target must be different files.")
    outputs = [p.resolve() for p in (args.json_out, args.markdown_out) if p]
    if len(set(outputs)) != len(outputs):
        raise ValueError("JSON and Markdown report paths must be different.")
    protected = {args.config.resolve(), source, target}
    if any(output in protected for output in outputs):
        raise ValueError("A report path cannot overwrite the configuration or either input extract.")


if __name__ == "__main__":
    raise SystemExit(main())
