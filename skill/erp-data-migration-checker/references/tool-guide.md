# Included CSV comparison CLI

This reference describes the companion `erp_migration_checker` package. It is available only when the package is present in the working environment; the skill itself does not install packages or access ERP systems.

## Invocation

From the package repository root:

```text
python -m erp_migration_checker --config mapping.json --source source.csv --target target.csv [--json-out report.json] [--markdown-out report.md] [--show-values]
```

The package can also be installed with `python -m pip install -e .`, which provides `erp-migration-check`.

Exit codes: `0` means no error-severity findings, `1` means the comparison completed with at least one error, and `2` means the configuration, inputs, or report destination could not be processed. A warning-only report exits `0` and identifies its status as `PASS_WITH_WARNINGS`.

## Supported mapping

The JSON object has these properties:

- `keys`: required non-empty array of `{ "source": "...", "target": "..." }` objects. Optional `trim` defaults to true; optional `case_insensitive` defaults to false. Composite keys are supported. Blank keys are errors. Duplicate keys are not paired arbitrarily.
- `fields`: required non-empty array. Each rule has `source`, `target`, and `type` (`string`, `decimal`, or `date`). Strings support `trim`, `case_insensitive`, and `allow_nulls`; defaults are true, false, and true. Decimal fields support a non-negative `tolerance` and `allow_nulls`. Date fields support `source_formats`, `target_formats`, and `allow_nulls`; accepted formats default to `%Y-%m-%d`. For all types, `allow_nulls` defaults to true.
- `aggregates`: optional array of `{ "name": "...", "source": "...", "target": "...", "tolerance": "..." }`. Totals use decimal arithmetic over non-null values from all input rows, including unmatched or duplicate-key rows.
- `null_tokens`: optional array of strings; comparison is case-insensitive after trimming. A blank CSV cell is always null even when the token list omits the empty string.
- `unmatched_source_severity`, `unmatched_target_severity`, `duplicate_severity`: optional `error` or `warning` values, each defaulting to `error`.
- `max_findings`: optional positive integer, default `1000`. Reaching the cap adds an error finding to make truncation visible.

Unknown properties and duplicate aggregate names are rejected. Mapped columns must exist, while extra CSV columns are ignored. Input extracts are loaded into memory. CSV data record references start at 2, treating the header as record 1 and ignoring blank lines.

## Report privacy

JSON and Markdown reports omit raw row values and keys by default. `--show-values` includes field mismatch values and aggregate totals. It does not add source or target business keys to reports. Protect any report generated with that flag as sensitive data.

The tool checks configured rules only. A `PASS` does not verify that the mapping is semantically correct, that every needed entity or partition was included, or that financial and operational policy was applied correctly.
