# ERP Migration Review Guide

Use this as a decision aid, not a substitute for the organization's approved migration plan or accounting policy.

## Establish the comparison population

Record the source and target system, entity, extraction timestamp, included subsidiaries or business units, accounting periods, statuses, and any filters. Confirm that both extracts represent the same migration run and cutoff. Reconcile record counts by meaningful partitions where practical; a grand total can conceal exclusions.

## Define keys and match behavior

- Prefer a stable business identifier or an approved composite key. A display name is rarely a safe identity key.
- Confirm case sensitivity, whitespace normalization, leading zeros, and null behavior before matching.
- Duplicate keys make a one-to-one comparison ambiguous. Resolve the identity rule or duplicates before accepting row-level results.
- Review missing target and target-only rows separately. They may be errors, intentional exclusions, or records outside the agreed scope.

## Map business meaning, not just labels

For each field, capture source field, target field, transformation, owner, and validation rule. Pay particular attention to:

- Transaction date versus posting date, period, timezone, and date-only versus timestamp behavior.
- Transaction currency versus base currency, currency precision, exchange-rate source and date, and rounding point.
- Debit/credit signs, positive and negative conventions, tax-inclusive versus tax-exclusive amounts, and gross/net fields.
- Internal IDs versus external IDs, renamed entities, inactive records, and parent-child references.
- Null, blank, zero, default, and "not applicable" values; these are not automatically equivalent.
- Statuses, units of measure, account classifications, subsidiary context, and effective-dated mappings.

## Select reconciliation controls

Choose controls that can expose different failure modes:

1. Population counts by entity and relevant partition.
2. Unique-key coverage and duplicate counts.
3. Required-field completeness and permitted-value checks.
4. Field-level comparisons after approved normalization.
5. Control totals by currency, subsidiary, period, account, or other relevant dimension.
6. Relationship checks across related entities, such as transaction-to-line and line-to-account mappings. The included CLI does not currently perform multi-file relationship checks.

Use decimal arithmetic for money. Set tolerances from the system's precision and the approved transformation design; do not widen them merely to make a comparison pass. State whether nulls are ignored, rejected, or expected to match.

## Triage exceptions

For each material finding, preserve the source and target row references, classify the cause, identify the business owner, record the resolution, and rerun the same controls after correction. Separate expected transformations from defects. Escalate unexplained differences and avoid manual edits to extracts that make the evidence non-reproducible.

## Evidence and sign-off

Keep the mapping version, extract identifiers and timestamps, configuration, report, exception disposition, rerun evidence, and approvals together under access controls. The comparison tool's PASS means its configured checks found no error-severity findings; it does not certify the mapping, accounting treatment, population completeness, or production cutover.
