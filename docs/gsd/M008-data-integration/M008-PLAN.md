# M008 Data Integration Plan

## Goal

Unify zhiceV1 data sources, remove silent mock/sample analysis, add field-level business validation, and prepare durable GSD auto artifacts for plan -> slice -> task execution.

## Source PRD

- `docs/gsd-input/zhicev1-data-integration-prd.md`
- `docs/maintenance/M008-DATA-INTEGRATION-AUDIT.md`

## Slices

- `S01-p0-data-unit-guardrails`: fix visible data unit bugs and add regression tests.
- `S02-source-inventory-no-mock`: inventory and classify mock/sample/static/fallback paths.
- `S03-tushare-cache-foundation`: add TuShare batch cache foundation.
- `S04-macro-industry-real-data`: replace macro/industry static data paths.
- `S05-gsd-automation-bootstrap`: make GSD preflight and durable artifacts runnable.

## Current Environment Finding

`gsd` CLI is not installed in the current shell. `gsd auto` cannot run until the CLI is installed and available on `PATH`.

## Acceptance

- P0 screenshot percentage issue fixed and covered by tests.
- Preflight reports GSD readiness clearly.
- Each slice has a durable plan file with verifiable tasks.
