from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Callable

from .model import (
    AggregateResult,
    CheckConfig,
    ComparisonReport,
    CsvRecord,
    FieldRule,
    Finding,
    KeyPair,
)


class DataError(ValueError):
    """Raised when an extract cannot be read or does not match its mapping."""


def compare_files(
    source_path: Path,
    target_path: Path,
    config: CheckConfig,
    include_values: bool = False,
) -> ComparisonReport:
    source_rows = _read_csv(source_path)
    target_rows = _read_csv(target_path)
    _require_columns({pair.source for pair in config.keys} | {rule.source for rule in config.fields} | {r.source for r in config.aggregates}, source_path)
    _require_columns({pair.target for pair in config.keys} | {rule.target for rule in config.fields} | {r.target for r in config.aggregates}, target_path)

    findings: list[Finding] = []
    truncated = False

    def add(finding: Finding) -> None:
        nonlocal truncated
        if len(findings) < config.max_findings:
            findings.append(finding)
        else:
            truncated = True

    source_groups, invalid_source_keys = _group_by_key(source_rows, config.keys, "source", config.null_tokens, add)
    target_groups, invalid_target_keys = _group_by_key(target_rows, config.keys, "target", config.null_tokens, add)

    duplicate_source = {key: rows for key, rows in source_groups.items() if len(rows) > 1}
    duplicate_target = {key: rows for key, rows in target_groups.items() if len(rows) > 1}
    for rows in duplicate_source.values():
        add(Finding(
            code="duplicate_source_key",
            severity=config.duplicate_severity,
            message=f"Source key appears {len(rows)} times; these rows cannot be matched safely.",
            source_rows=[row.row_number for row in rows],
        ))
    for rows in duplicate_target.values():
        add(Finding(
            code="duplicate_target_key",
            severity=config.duplicate_severity,
            message=f"Target key appears {len(rows)} times; these rows cannot be matched safely.",
            target_rows=[row.row_number for row in rows],
        ))

    all_keys = sorted(set(source_groups) | set(target_groups))
    matched: list[tuple[CsvRecord, CsvRecord]] = []
    unmatched_source = 0
    unmatched_target = 0
    for key in all_keys:
        source_matches = source_groups.get(key, [])
        target_matches = target_groups.get(key, [])
        if len(source_matches) > 1 or len(target_matches) > 1:
            continue
        if source_matches and target_matches:
            matched.append((source_matches[0], target_matches[0]))
        elif source_matches:
            unmatched_source += 1
            add(Finding(
                code="missing_target_row",
                severity=config.unmatched_source_severity,
                message="Source row has no unique matching target row.",
                source_rows=[source_matches[0].row_number],
            ))
        elif target_matches:
            unmatched_target += 1
            add(Finding(
                code="unexpected_target_row",
                severity=config.unmatched_target_severity,
                message="Target row has no unique matching source row.",
                target_rows=[target_matches[0].row_number],
            ))

    compared_cells = 0
    mismatched_cells = 0
    for source_record, target_record in matched:
        for rule in config.fields:
            compared_cells += 1
            issue = _compare_field(source_record, target_record, rule, config.null_tokens)
            if issue is None:
                continue
            mismatched_cells += 1
            code, message, source_value, target_value = issue
            add(Finding(
                code=code,
                severity="error",
                message=message,
                source_rows=[source_record.row_number],
                target_rows=[target_record.row_number],
                field=f"{rule.source} -> {rule.target}",
                source_value=source_value if include_values else None,
                target_value=target_value if include_values else None,
            ))

    aggregates: list[AggregateResult] = []
    for rule in config.aggregates:
        aggregate, issue = _aggregate(source_rows, target_rows, rule.name, rule.source, rule.target, rule.tolerance, config.null_tokens)
        aggregates.append(aggregate)
        if issue is not None:
            code, message, source_bad, target_bad = issue
            add(Finding(
                code=code,
                severity="error",
                message=message,
                source_rows=source_bad,
                target_rows=target_bad,
                field=f"{rule.source} -> {rule.target}",
            ))
        elif aggregate.within_tolerance is False:
            add(Finding(
                code="aggregate_mismatch",
                severity="error",
                message=f"Aggregate '{rule.name}' differs by more than its configured tolerance.",
                field=f"{rule.source} -> {rule.target}",
                source_value=str(aggregate.source_total) if include_values else None,
                target_value=str(aggregate.target_total) if include_values else None,
            ))

    if truncated:
        findings.append(Finding(
            code="findings_truncated",
            severity="error",
            message=f"Finding limit of {config.max_findings} reached; additional findings were omitted.",
        ))

    return ComparisonReport(
        source_file=source_path.name,
        target_file=target_path.name,
        source_row_count=len(source_rows),
        target_row_count=len(target_rows),
        matched_key_count=len(matched),
        unmatched_source_count=unmatched_source,
        unmatched_target_count=unmatched_target,
        duplicate_source_groups=len(duplicate_source),
        duplicate_target_groups=len(duplicate_target),
        invalid_key_row_count=len(invalid_source_keys) + len(invalid_target_keys),
        compared_field_cells=compared_cells,
        mismatched_field_cells=mismatched_cells,
        findings=findings,
        aggregates=aggregates,
        findings_truncated=truncated,
    )


def _read_csv(path: Path) -> list[CsvRecord]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            try:
                headers = next(reader)
            except StopIteration as exc:
                raise DataError(f"{path.name} is empty and has no header row.") from exc
            if not headers or any(not header.strip() for header in headers):
                raise DataError(f"{path.name} contains a blank column name.")
            if len(set(headers)) != len(headers):
                raise DataError(f"{path.name} contains duplicate column names.")
            rows: list[CsvRecord] = []
            record_number = 1
            for values in reader:
                if not values:
                    continue
                record_number += 1
                if len(values) != len(headers):
                    raise DataError(
                        f"{path.name} has {len(values)} values for {len(headers)} columns on CSV line {reader.line_num}."
                    )
                rows.append(CsvRecord(row_number=record_number, values=dict(zip(headers, values))))
            return rows
    except OSError as exc:
        raise DataError(f"Could not read {path.name}: {exc}") from exc
    except csv.Error as exc:
        raise DataError(f"Could not parse {path.name}: {exc}") from exc


def _require_columns(required: set[str], path: Path) -> None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            headers = next(csv.reader(stream), [])
    except OSError as exc:
        raise DataError(f"Could not read {path.name}: {exc}") from exc
    missing = sorted(required - set(headers))
    if missing:
        raise DataError(f"{path.name} is missing mapped column(s): {', '.join(missing)}.")


def _group_by_key(
    rows: list[CsvRecord],
    pairs: tuple[KeyPair, ...],
    side: str,
    null_tokens: frozenset[str],
    add_finding: Callable[[Finding], None],
) -> tuple[dict[tuple[str, ...], list[CsvRecord]], list[int]]:
    groups: dict[tuple[str, ...], list[CsvRecord]] = defaultdict(list)
    invalid_rows: list[int] = []
    for row in rows:
        pieces: list[str] = []
        for pair in pairs:
            column = pair.source if side == "source" else pair.target
            raw = row.values[column]
            if _is_null(raw, null_tokens):
                invalid_rows.append(row.row_number)
                add_finding(Finding(
                    code="blank_key",
                    severity="error",
                    message=f"Row has a blank value in mapped key column '{column}'.",
                    source_rows=[row.row_number] if side == "source" else [],
                    target_rows=[row.row_number] if side == "target" else [],
                    field=column,
                ))
                pieces = []
                break
            normalized = raw.strip() if pair.trim else raw
            if pair.case_insensitive:
                normalized = normalized.casefold()
            pieces.append(normalized)
        if pieces:
            groups[tuple(pieces)].append(row)
    return groups, invalid_rows


def _compare_field(
    source: CsvRecord,
    target: CsvRecord,
    rule: FieldRule,
    null_tokens: frozenset[str],
) -> tuple[str, str, str | None, str | None] | None:
    source_raw = source.values[rule.source]
    target_raw = target.values[rule.target]
    source_null = _is_null(source_raw, null_tokens)
    target_null = _is_null(target_raw, null_tokens)
    if source_null or target_null:
        if source_null and target_null:
            if not rule.allow_nulls:
                return ("null_value_not_allowed", "Both sides are blank or null for a field configured as required.", None, None)
            return None
        return (
            "null_mismatch",
            "One side is blank or null while the other contains a value.",
            None if source_null else source_raw,
            None if target_null else target_raw,
        )

    if rule.kind == "string":
        left = source_raw.strip() if rule.trim else source_raw
        right = target_raw.strip() if rule.trim else target_raw
        if rule.case_insensitive:
            left, right = left.casefold(), right.casefold()
        if left == right:
            return None
        return ("field_mismatch", "Mapped string values differ.", source_raw, target_raw)

    if rule.kind == "decimal":
        left = _parse_decimal(source_raw)
        right = _parse_decimal(target_raw)
        if left is None:
            return ("invalid_source_decimal", "Source value is not a valid finite decimal.", source_raw, None)
        if right is None:
            return ("invalid_target_decimal", "Target value is not a valid finite decimal.", None, target_raw)
        if _within_tolerance(left, right, rule.tolerance):
            return None
        return ("decimal_mismatch", "Mapped decimal values exceed the configured tolerance.", source_raw, target_raw)

    left_date = _parse_date(source_raw, rule.source_formats)
    right_date = _parse_date(target_raw, rule.target_formats)
    if left_date is None:
        return ("invalid_source_date", "Source value does not match any configured date format.", source_raw, None)
    if right_date is None:
        return ("invalid_target_date", "Target value does not match any configured date format.", None, target_raw)
    if left_date == right_date:
        return None
    return ("date_mismatch", "Mapped calendar dates differ.", source_raw, target_raw)


def _aggregate(
    source_rows: list[CsvRecord],
    target_rows: list[CsvRecord],
    name: str,
    source_field: str,
    target_field: str,
    tolerance: Decimal,
    null_tokens: frozenset[str],
) -> tuple[AggregateResult, tuple[str, str, list[int], list[int]] | None]:
    source_total, bad_source = _sum_field(source_rows, source_field, null_tokens)
    target_total, bad_target = _sum_field(target_rows, target_field, null_tokens)
    if bad_source or bad_target:
        result = AggregateResult(
            name=name,
            source_field=source_field,
            target_field=target_field,
            tolerance=tolerance,
            source_total=None,
            target_total=None,
            difference=None,
            within_tolerance=None,
            invalid_source_rows=bad_source,
            invalid_target_rows=bad_target,
        )
        return result, (
            "aggregate_invalid_decimal",
            f"Aggregate '{name}' could not be evaluated because one or more non-null values are invalid decimals.",
            bad_source,
            bad_target,
        )
    with localcontext() as context:
        context.prec = _working_precision([source_total, target_total], 2)
        difference = abs(source_total - target_total)
    result = AggregateResult(
        name=name,
        source_field=source_field,
        target_field=target_field,
        tolerance=tolerance,
        source_total=source_total,
        target_total=target_total,
        difference=difference,
        within_tolerance=difference <= tolerance,
    )
    return result, None


def _sum_field(
    rows: list[CsvRecord],
    column: str,
    null_tokens: frozenset[str],
) -> tuple[Decimal, list[int]]:
    values: list[Decimal] = []
    invalid: list[int] = []
    for row in rows:
        raw = row.values[column]
        if _is_null(raw, null_tokens):
            continue
        value = _parse_decimal(raw)
        if value is None:
            invalid.append(row.row_number)
        else:
            values.append(value)
    with localcontext() as context:
        context.prec = _working_precision(values, len(values))
        total = sum(values, Decimal("0"))
    return total, invalid


def _within_tolerance(left: Decimal, right: Decimal, tolerance: Decimal) -> bool:
    with localcontext() as context:
        context.prec = _working_precision([left, right, tolerance], 3)
        return abs(left - right) <= tolerance


def _working_precision(values: list[Decimal], item_count: int) -> int:
    if not values:
        return 28
    minimum_exponent = min(value.as_tuple().exponent for value in values)
    maximum_adjusted = max(value.adjusted() for value in values)
    carry_digits = len(str(max(item_count, 1)))
    return max(28, maximum_adjusted - minimum_exponent + carry_digits + 3)


def _parse_decimal(value: str) -> Decimal | None:
    try:
        parsed = Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _parse_date(value: str, formats: tuple[str, ...]) -> date | None:
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _is_null(value: str | None, null_tokens: frozenset[str]) -> bool:
    return value is None or value.strip().casefold() in null_tokens
