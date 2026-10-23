from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .model import AggregateRule, CheckConfig, FieldRule, KeyPair


class ConfigError(ValueError):
    """Raised when a migration mapping is invalid or ambiguous."""


def load_config(path: Path) -> CheckConfig:
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            raw = json.load(stream)
    except OSError as exc:
        raise ConfigError(f"Could not read configuration: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration is not valid JSON at line {exc.lineno}: {exc.msg}") from exc
    except UnicodeError as exc:
        raise ConfigError("Configuration must be UTF-8 JSON.") from exc

    root = _object(raw, "configuration")
    _only_keys(
        root,
        {
            "keys",
            "fields",
            "aggregates",
            "null_tokens",
            "unmatched_source_severity",
            "unmatched_target_severity",
            "duplicate_severity",
            "max_findings",
        },
        "configuration",
    )

    raw_keys = root.get("keys")
    if not isinstance(raw_keys, list) or not raw_keys:
        raise ConfigError("'keys' must be a non-empty list of source/target column pairs.")
    keys = tuple(_column_pair(item, f"keys[{index}]") for index, item in enumerate(raw_keys))
    if len({pair.source for pair in keys}) != len(keys) or len({pair.target for pair in keys}) != len(keys):
        raise ConfigError("Each source and target key column may appear only once.")

    raw_fields = root.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ConfigError("'fields' must be a non-empty list of field comparison rules.")
    fields = tuple(_field_rule(item, index) for index, item in enumerate(raw_fields))
    field_pairs = [(rule.source, rule.target) for rule in fields]
    if len(set(field_pairs)) != len(field_pairs):
        raise ConfigError("Each source/target field pair may be configured only once.")

    raw_aggregates = root.get("aggregates", [])
    if not isinstance(raw_aggregates, list):
        raise ConfigError("'aggregates' must be a list.")
    aggregates = tuple(_aggregate_rule(item, index) for index, item in enumerate(raw_aggregates))
    if len({rule.name for rule in aggregates}) != len(aggregates):
        raise ConfigError("Aggregate check names must be unique.")

    null_tokens = root.get("null_tokens", ["", "null", "none"])
    if not isinstance(null_tokens, list) or any(not isinstance(v, str) for v in null_tokens):
        raise ConfigError("'null_tokens' must be a list of strings.")
    null_set = frozenset({""} | {value.strip().casefold() for value in null_tokens})

    max_findings = root.get("max_findings", 1000)
    if isinstance(max_findings, bool) or not isinstance(max_findings, int) or max_findings < 1:
        raise ConfigError("'max_findings' must be a positive integer.")

    return CheckConfig(
        keys=keys,
        fields=fields,
        aggregates=aggregates,
        null_tokens=null_set,
        unmatched_source_severity=_severity(root.get("unmatched_source_severity", "error"), "unmatched_source_severity"),
        unmatched_target_severity=_severity(root.get("unmatched_target_severity", "error"), "unmatched_target_severity"),
        duplicate_severity=_severity(root.get("duplicate_severity", "error"), "duplicate_severity"),
        max_findings=max_findings,
    )


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a JSON object.")
    return value


def _only_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"Unknown {label} setting(s): {', '.join(unknown)}.")


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} must be a non-empty string.")
    return value.strip()


def _column_pair(value: Any, label: str) -> KeyPair:
    item = _object(value, label)
    _only_keys(item, {"source", "target", "trim", "case_insensitive"}, label)
    trim = item.get("trim", True)
    case_insensitive = item.get("case_insensitive", False)
    if not isinstance(trim, bool) or not isinstance(case_insensitive, bool):
        raise ConfigError(f"{label}.trim and case_insensitive must be booleans.")
    return KeyPair(
        source=_nonempty_string(item.get("source"), f"{label}.source"),
        target=_nonempty_string(item.get("target"), f"{label}.target"),
        trim=trim,
        case_insensitive=case_insensitive,
    )


def _field_rule(value: Any, index: int) -> FieldRule:
    label = f"fields[{index}]"
    item = _object(value, label)
    allowed = {
        "source", "target", "type", "tolerance", "source_formats", "target_formats", "trim", "case_insensitive", "allow_nulls"
    }
    _only_keys(item, allowed, label)
    source = _nonempty_string(item.get("source"), f"{label}.source")
    target = _nonempty_string(item.get("target"), f"{label}.target")
    kind = item.get("type", "string")
    if not isinstance(kind, str) or kind not in {"string", "decimal", "date"}:
        raise ConfigError(f"{label}.type must be 'string', 'decimal', or 'date'.")

    tolerance = _decimal(item.get("tolerance", "0"), f"{label}.tolerance")
    if tolerance < 0:
        raise ConfigError(f"{label}.tolerance cannot be negative.")

    source_formats = _formats(item.get("source_formats", ["%Y-%m-%d"]), f"{label}.source_formats")
    target_formats = _formats(item.get("target_formats", ["%Y-%m-%d"]), f"{label}.target_formats")
    trim = item.get("trim", True)
    case_insensitive = item.get("case_insensitive", False)
    allow_nulls = item.get("allow_nulls", True)
    if not isinstance(trim, bool) or not isinstance(case_insensitive, bool) or not isinstance(allow_nulls, bool):
        raise ConfigError(f"{label}.trim, case_insensitive, and allow_nulls must be booleans.")
    if kind != "decimal" and "tolerance" in item:
        raise ConfigError(f"{label}.tolerance is only valid for decimal fields.")
    if kind != "date" and ("source_formats" in item or "target_formats" in item):
        raise ConfigError(f"{label}.source_formats and target_formats are only valid for date fields.")
    if kind != "string" and ("trim" in item or "case_insensitive" in item):
        raise ConfigError(f"{label}.trim and case_insensitive are only valid for string fields.")

    return FieldRule(
        source=source,
        target=target,
        kind=kind,
        tolerance=tolerance,
        source_formats=source_formats,
        target_formats=target_formats,
        trim=trim,
        case_insensitive=case_insensitive,
        allow_nulls=allow_nulls,
    )


def _aggregate_rule(value: Any, index: int) -> AggregateRule:
    label = f"aggregates[{index}]"
    item = _object(value, label)
    _only_keys(item, {"name", "source", "target", "tolerance"}, label)
    tolerance = _decimal(item.get("tolerance", "0"), f"{label}.tolerance")
    if tolerance < 0:
        raise ConfigError(f"{label}.tolerance cannot be negative.")
    return AggregateRule(
        name=_nonempty_string(item.get("name"), f"{label}.name"),
        source=_nonempty_string(item.get("source"), f"{label}.source"),
        target=_nonempty_string(item.get("target"), f"{label}.target"),
        tolerance=tolerance,
    )


def _formats(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v for v in value):
        raise ConfigError(f"{label} must be a non-empty list of date format strings.")
    return tuple(value)


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ConfigError(f"{label} must be a non-negative decimal value.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ConfigError(f"{label} is not a valid decimal value.") from exc
    if not number.is_finite():
        raise ConfigError(f"{label} must be finite.")
    if abs(number.as_tuple().exponent) > 1000 or len(number.as_tuple().digits) > 1000:
        raise ConfigError(f"{label} exceeds supported decimal precision or exponent (1000).")
    return number


def _severity(value: Any, label: str) -> str:
    if not isinstance(value, str) or value not in {"error", "warning"}:
        raise ConfigError(f"{label} must be 'error' or 'warning'.")
    return value
