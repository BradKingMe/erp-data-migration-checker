# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: preserve the existing Python migration-checker engine and add an optional Streamlit review interface. The current comparison engine remains the source of truth.

## Users

ERP migration analysts and finance reviewers comparing source-system and target-system CSV extracts.

## Product Purpose

Help a reviewer define explicit field mappings, run a migration comparison, investigate exceptions, and package the evidence for review.

## Positioning

The interface makes the existing deterministic comparison rules visible and reviewable. It does not guess business mappings or connect to live ERP systems.

## Operating Context

The app runs locally with a bundled synthetic invoice example or a pair of user-provided CSV exports. Reviewers can inspect row references, configure comparison rules, and download a report bundle.

## Capabilities and Constraints

- Reuses the current engine for composite keys, duplicate and unmatched rows, string/decimal/date comparisons, tolerances, and aggregate checks.
- Supports local CSV upload, explicit mappings, exception review, and evidence export.
- No NetSuite, SAS, database, or other live-system connection is in scope.
- Raw comparison values are hidden from exported reports by default; real data should be reviewed only in a local run.
- Existing CLI behavior and the included migration skill remain intact.

## Evidence on Hand

The repository contains a standard-library Python comparison engine and synthetic invoice fixtures with intentional differences. No customer data, production validation, or customer endorsement is available; do not imply otherwise.

## Product Principles

- Keep comparison behavior deterministic and mappings explicit.
- Put actionable exceptions and their source/target row references at the center of review.
- Preserve exact decimal arithmetic for financial fields.
- Make privacy choices clear before showing or exporting row values.
- Keep the CLI available alongside the optional interface.
