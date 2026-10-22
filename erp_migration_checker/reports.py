from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .model import ComparisonReport


def json_report(report: ComparisonReport, include_values: bool = False) -> str:
    return json.dumps(report.to_dict(include_values), indent=2, ensure_ascii=False) + "\n"


def markdown_report(report: ComparisonReport, include_values: bool = False) -> str:
    payload = report.to_dict(include_values)
    summary = payload["summary"]
    lines = [
        f"# Migration comparison: {report.status}",
        "",
        f"- Source extract: `{_cell(report.source_file)}` ({report.source_row_count} rows)",
        f"- Target extract: `{_cell(report.target_file)}` ({report.target_row_count} rows)",
        f"- Matched unique keys: {report.matched_key_count}",
        f"- Findings: {summary['errors']} error(s), {summary['warnings']} warning(s)",
        f"- Raw row values included: {'yes' if include_values else 'no'}",
        "",
        "## Summary",
        "",
        "| Measure | Count |",
        "| --- | ---: |",
        f"| Unmatched source rows | {report.unmatched_source_count} |",
        f"| Unmatched target rows | {report.unmatched_target_count} |",
        f"| Duplicate source key groups | {report.duplicate_source_groups} |",
        f"| Duplicate target key groups | {report.duplicate_target_groups} |",
        f"| Invalid key rows | {report.invalid_key_row_count} |",
        f"| Compared field cells | {report.compared_field_cells} |",
        f"| Mismatched field cells | {report.mismatched_field_cells} |",
        "",
        "## Aggregate checks",
        "",
    ]
    if report.aggregates:
        lines.extend([
            "| Check | Status | Tolerance | Source total | Target total |",
            "| --- | --- | ---: | ---: | ---: |",
        ])
        for aggregate in report.aggregates:
            state = "not evaluated" if aggregate.within_tolerance is None else ("pass" if aggregate.within_tolerance else "fail")
            source_total = _cell(str(aggregate.source_total)) if include_values and aggregate.source_total is not None else "redacted"
            target_total = _cell(str(aggregate.target_total)) if include_values and aggregate.target_total is not None else "redacted"
            lines.append(
                f"| {_cell(aggregate.name)} | {state} | {aggregate.tolerance} | {source_total} | {target_total} |"
            )
    else:
        lines.append("No aggregate checks configured.")
    lines.extend(["", "## Findings", ""])
    if report.findings:
        lines.extend([
            "| Severity | Code | Field | Source rows | Target rows | Finding |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for finding in report.findings:
            source_rows = ", ".join(f"S{n}" for n in finding.source_rows) or "—"
            target_rows = ", ".join(f"T{n}" for n in finding.target_rows) or "—"
            message = finding.message
            if include_values and (finding.source_value is not None or finding.target_value is not None):
                message += f" Source={finding.source_value!r}; target={finding.target_value!r}."
            lines.append(
                f"| {finding.severity} | `{_cell(finding.code)}` | {_cell(finding.field or '—')} | "
                f"{source_rows} | {target_rows} | {_cell(message)} |"
            )
    else:
        lines.append("No findings.")
    if report.findings_truncated:
        lines.extend(["", "> Finding output was truncated at the configured limit."])
    lines.extend([
        "",
        "## Review note",
        "",
        "This report checks only the configured CSV-level rules. A passing result does not prove that the mapping is complete, that accounting policy is correct, or that the target ERP is ready for production. Obtain business-owner sign-off for migration controls.",
        "",
    ])
    return "\n".join(lines)


def write_report(path: Path, content: str, protected_inputs: tuple[Path, ...]) -> None:
    destination = path.resolve()
    if any(destination == item.resolve() for item in protected_inputs):
        raise ValueError(f"Report path {path.name} would overwrite an input file.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_name = stream.name
            stream.write(content)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")
