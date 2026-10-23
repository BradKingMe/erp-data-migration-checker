# ERP Data Migration Checker

A small, local-first command-line tool for comparing source and target ERP CSV extracts against an explicit mapping. It checks record identity, configured fields, duplicate keys, unmatched records, and numeric control totals, then writes JSON and Markdown reports.

It has no runtime dependencies beyond Python's standard library. It does not connect to NetSuite, SAS, databases, or any other live system.

## Quick start

Requires Python 3.10 or newer.

```powershell
python -m erp_migration_checker `
  --config examples/migration.json `
  --source examples/source_invoices.csv `
  --target examples/target_invoices.csv `
  --json-out reports/invoice-comparison.json `
  --markdown-out reports/invoice-comparison.md
```

The included extracts intentionally contain differences, so this example exits with code `1` after producing its reports. It demonstrates a missing target row, an unexpected target row, a duplicate target key, a date difference, a decimal difference, and a total mismatch. Exit code `0` means no error-severity findings; `2` means configuration, input, or report-writing failure.

Install the console command if you prefer:

```powershell
python -m pip install -e .
erp-migration-check --config examples/migration.json --source examples/source_invoices.csv --target examples/target_invoices.csv
```

## Interactive Migration Workbench

The optional Streamlit interface adds an exception review desk around the same comparison engine. It starts with bundled synthetic invoices, supports local CSV uploads, lets you edit key, field, and aggregate mappings, and exports a redacted audit pack.

```powershell
python -m pip install -e ".[ui]"
python -m streamlit run app.py
```

The app processes uploads in the running Streamlit process and uses short-lived temporary files only while the existing engine compares the extracts. A local run stays on your computer. If you deploy the app to a hosted server, that server processes the uploaded files. Values from uploaded files are hidden in the review screen by default; the bundled synthetic example shows its sample values. The default audit pack redacts values. Including source extracts in the ZIP is optional and off by default.

The interface does not connect to NetSuite, SAS, databases, or other live systems. It is a CSV review layer; mappings, tolerances, populations, and cutover sign-off remain business decisions.

## What it checks

- Joins records on one or more explicitly mapped key columns. Key values are trimmed by default and remain case-sensitive unless configured otherwise.
- Detects blank keys and duplicate keys. Rows with ambiguous duplicate keys are not paired arbitrarily.
- Reports source rows with no unique target match and target rows with no unique source match. Each side's severity is configurable.
- Compares mapped strings, decimals, and dates. Decimal tolerance, accepted date formats, case handling, and whether a field may be null are explicit in the configuration. Null-like tokens are treated as null on both sides; blank CSV values are always null.
- Checks configured decimal totals across each complete extract. A total ignores null-like values and includes all other rows, including rows with duplicate or unmatched keys. Mark required mapped fields with `"allow_nulls": false` to flag nulls in matched records.
- Writes a structured JSON report, a review-friendly Markdown report, or both.

See [`examples/migration.json`](examples/migration.json) for the mapping format. Unknown configuration keys are rejected so typos do not silently change the comparison.

### Configuration rules

- `keys` maps one or more source columns to target columns. Each side's key columns must be unique. `trim` defaults to `true`; `case_insensitive` defaults to `false`.
- `fields` maps columns and supports `string`, `decimal`, or `date`. Strings trim by default and compare case-sensitively unless configured otherwise. Dates default to `%Y-%m-%d`; `source_formats` and `target_formats` can provide ordered format lists. Decimal values use `Decimal` arithmetic and accept an optional non-negative `tolerance`.
- `allow_nulls` defaults to `true` for a field. Set it to `false` to report a finding when both matched values are null. One-null/one-value always produces a finding. Blank CSV cells are always null; `null_tokens` adds case-insensitive null spellings such as `null` or `n/a`.
- `aggregates` maps decimal columns and compares their totals using a non-negative tolerance. Null-like values are skipped. Totals include duplicate-key and unmatched rows; compare partitions separately when currencies, subsidiaries, periods, or other dimensions must not net against one another.
- `unmatched_source_severity`, `unmatched_target_severity`, and `duplicate_severity` accept `error` or `warning` and default to `error`. `max_findings` defaults to 1,000; if reached, an explicit error finding reports that output was truncated.
- Mapped columns must exist in their respective extracts. Unmapped extra columns are allowed. Duplicate headers, malformed row widths, and invalid configuration stop the run with exit code `2`.
- Extracts must be comma-delimited UTF-8 CSV files; an optional UTF-8 byte-order mark is accepted.

Finding references such as `S2` and `T2` are logical CSV record numbers, with the header as record 1. Blank lines are ignored.

## Privacy

Reports omit raw field values and record keys by default. They use CSV row references and mapped column names to identify findings. `--show-values` explicitly includes compared values and aggregate totals in the output; those reports can contain financial or business-sensitive information. Store them accordingly and do not commit real extracts or reports to a public repository.

The checker reads the supplied files and writes only the explicitly requested report files. It does not upload or transmit extract contents.

## Skill included

The [`skill/erp-data-migration-checker`](skill/erp-data-migration-checker/) directory contains an installable Codex skill. It guides an agent through migration scope, mapping semantics, reconciliation controls, exception review, and report interpretation. The skill distinguishes business decisions from what this CSV comparison tool can measure.

## Deliberate limits

This release compares one source CSV with one target CSV at a time and loads both extracts into memory. It does not infer a mapping, validate foreign-key relationships across multiple files, interpret ERP accounting policy, assess tax or currency conversion rules, or certify a production cutover. A zero-error report means only that the configured checks passed. A business owner should approve the mapping, tolerances, null handling, populations, and final reconciliation evidence.

## License

MIT. See [`LICENSE`](LICENSE).

## Code audit and limits

The CLI and interface accept up to 25 MB per extract, 100,000 data rows, 1,000 columns, and 1,000,000 data cells. Unsupported input is rejected rather than partially compared. CSV parsing uses strict quote handling and rejects invalid UTF-8 and NUL text. Decimal values and tolerances support up to 1,000 significant digits and exponent magnitude 1,000; larger numbers are rejected as invalid.

Run `python -m unittest discover -s tests -p test_engine.py` for standalone engine checks. With the UI extra installed, run `python tests/run_audit.py` for Streamlit state, report, and privacy checks. The audit used Streamlit 1.66.1 on Windows; older supported versions have not all been executed. Upload controls use the version-compatible global size setting plus parser limits.
