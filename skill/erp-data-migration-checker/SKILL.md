---
name: erp-data-migration-checker
description: Plan and review ERP data migrations by defining mappings, keys, normalization, reconciliation controls, and exception handling. Use when comparing source and target extracts or preparing migration validation evidence; it does not connect to live ERP systems.
---

# ERP Data Migration Checker

Help the user make ERP migration comparisons explicit, reproducible, and reviewable. Treat the mapping and control design as business decisions that need an owner. Do not claim that a CSV comparison proves a full migration is correct.

## Workflow

1. Establish the source and target systems, entity or table, extract scope and dates, migration run, and intended population. Ask only for details that affect the comparison. Do not assume two similarly named fields have identical business meaning.
2. Define the record identity. Confirm whether the key is single-column or composite, whether it is case-sensitive, and how whitespace and nulls are treated. Confirm the expected behavior for duplicates, missing target records, and target-only records.
3. Map each compared field and its semantics. Choose the comparison type, accepted date formats, decimal precision and tolerance, string normalization, and whether nulls are allowed. For amounts, confirm currency, sign convention, rounding stage, and whether the field is transaction, base, or reporting currency.
4. Define control totals and population checks that match the business question. Totals should be segmented when a single grand total could hide offsetting errors, such as by currency, subsidiary, account, period, or entity. Do not invent a tolerance; ask the responsible owner or mark it as a decision needed.
5. If the `erp_migration_checker` package is present and the inputs are CSV extracts, write or review a JSON mapping and run the CLI from the project root. The tool compares one CSV to one CSV. For other formats, multiple related files, live ERP access, or unsupported rules, explain the gap and prepare an equivalent review plan without implying the CLI handled it.
6. Review the report by finding category and record references. Resolve duplicate keys before trusting row-level comparisons. Trace material exceptions to source records and business rules; distinguish expected transformations from defects.
7. Present the outcome with scope, mapping assumptions, control totals, exceptions, unresolved decisions, severity, owner, and evidence. A passing configured comparison is evidence for those checks only. Obtain business-owner approval for reconciliation and cutover readiness.

## Operating boundaries

- Treat supplied extracts as potentially confidential. Avoid exposing raw records in chat. Prefer reports with values omitted; the CLI includes raw values only when `--show-values` is explicitly supplied.
- Do not connect to, mutate, or import data into NetSuite or another system unless the user explicitly requests that separate action and the available tools support it.
- Never invent field mappings, accounting treatment, tolerances, record populations, or approval status. Record an open decision instead.
- Do not describe duplicate or unmatched rows as automatically wrong. Their meaning and severity depend on the approved migration scope.
- Do not infer completeness from a grand-total match; offsetting errors, excluded populations, duplicate rows, or wrong currency treatment can produce a false reconciliation.

For the review framework and common ERP-specific pitfalls, read [references/migration-review-guide.md](references/migration-review-guide.md). When using the included CLI, read [references/tool-guide.md](references/tool-guide.md) for its exact input and reporting behavior. If working from the source repository, inspect its README and example mapping before creating a configuration.
