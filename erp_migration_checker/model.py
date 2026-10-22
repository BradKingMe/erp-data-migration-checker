from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class KeyPair:
    source: str
    target: str
    trim: bool = True
    case_insensitive: bool = False


@dataclass(frozen=True)
class FieldRule:
    source: str
    target: str
    kind: str
    tolerance: Decimal = Decimal("0")
    source_formats: tuple[str, ...] = ("%Y-%m-%d",)
    target_formats: tuple[str, ...] = ("%Y-%m-%d",)
    trim: bool = True
    case_insensitive: bool = False
    allow_nulls: bool = True


@dataclass(frozen=True)
class AggregateRule:
    name: str
    source: str
    target: str
    tolerance: Decimal


@dataclass(frozen=True)
class CheckConfig:
    keys: tuple[KeyPair, ...]
    fields: tuple[FieldRule, ...]
    aggregates: tuple[AggregateRule, ...]
    null_tokens: frozenset[str]
    unmatched_source_severity: str
    unmatched_target_severity: str
    duplicate_severity: str
    max_findings: int


@dataclass(frozen=True)
class CsvRecord:
    row_number: int
    values: dict[str, str]


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    source_rows: list[int] = field(default_factory=list)
    target_rows: list[int] = field(default_factory=list)
    field: str | None = None
    source_value: str | None = None
    target_value: str | None = None

    def to_dict(self, include_values: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source_rows": self.source_rows,
            "target_rows": self.target_rows,
        }
        if self.field is not None:
            result["field"] = self.field
        if include_values:
            if self.source_value is not None:
                result["source_value"] = self.source_value
            if self.target_value is not None:
                result["target_value"] = self.target_value
        return result


@dataclass
class AggregateResult:
    name: str
    source_field: str
    target_field: str
    tolerance: Decimal
    source_total: Decimal | None
    target_total: Decimal | None
    difference: Decimal | None
    within_tolerance: bool | None
    invalid_source_rows: list[int] = field(default_factory=list)
    invalid_target_rows: list[int] = field(default_factory=list)

    def to_dict(self, include_values: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "source_field": self.source_field,
            "target_field": self.target_field,
            "tolerance": str(self.tolerance),
            "within_tolerance": self.within_tolerance,
            "invalid_source_rows": self.invalid_source_rows,
            "invalid_target_rows": self.invalid_target_rows,
        }
        if include_values:
            result["source_total"] = _decimal_text(self.source_total)
            result["target_total"] = _decimal_text(self.target_total)
            result["absolute_difference"] = _decimal_text(self.difference)
        return result


@dataclass
class ComparisonReport:
    source_file: str
    target_file: str
    source_row_count: int
    target_row_count: int
    matched_key_count: int
    unmatched_source_count: int
    unmatched_target_count: int
    duplicate_source_groups: int
    duplicate_target_groups: int
    invalid_key_row_count: int
    compared_field_cells: int
    mismatched_field_cells: int
    findings: list[Finding]
    aggregates: list[AggregateResult]
    findings_truncated: bool = False

    @property
    def status(self) -> str:
        if any(f.severity == "error" for f in self.findings):
            return "FAIL"
        if any(f.severity == "warning" for f in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def to_dict(self, include_values: bool = False) -> dict[str, Any]:
        errors = sum(f.severity == "error" for f in self.findings)
        warnings = sum(f.severity == "warning" for f in self.findings)
        return {
            "schema_version": 1,
            "status": self.status,
            "source_file": self.source_file,
            "target_file": self.target_file,
            "summary": {
                "source_rows": self.source_row_count,
                "target_rows": self.target_row_count,
                "matched_keys": self.matched_key_count,
                "unmatched_source_rows": self.unmatched_source_count,
                "unmatched_target_rows": self.unmatched_target_count,
                "duplicate_source_key_groups": self.duplicate_source_groups,
                "duplicate_target_key_groups": self.duplicate_target_groups,
                "invalid_key_rows": self.invalid_key_row_count,
                "compared_field_cells": self.compared_field_cells,
                "mismatched_field_cells": self.mismatched_field_cells,
                "errors": errors,
                "warnings": warnings,
                "findings_truncated": self.findings_truncated,
            },
            "privacy": {
                "raw_values_included": include_values,
                "row_keys_included": False,
            },
            "aggregates": [a.to_dict(include_values) for a in self.aggregates],
            "findings": [f.to_dict(include_values) for f in self.findings],
        }


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
