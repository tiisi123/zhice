# S06 PRD Closure Plan

## Objective

Close the five remaining gaps from `docs/gsd-input/zhicev1-data-integration-prd.md` with verifiable code, tests, and automation support.

## Tasks

- [x] T01: Make ETF and backtest routes default to `auto` / live-cache-first behavior.
  - Files: `prototype/apps/api/routes/backtest.py`, ETF/backtest UI panels, related tests.
  - Verify: focused API tests and web build.

- [x] T02: Ensure production-critical data routes expose `data_source`, `data_mode`, `as_of`, and `fallback_reason`.
  - Files: ETF, backtest, growth/value routes.
  - Verify: integration contract tests.

- [x] T03: Add `prototype/tests/integration/test_data_sources.py`.
  - Coverage: ETF cache path, macro live/fallback metadata, valuation unavailable/field contract.
  - Verify: `python -m pytest tests/integration/test_data_sources.py`.

- [x] T04: Resolve sample/static user-visible routes by marking them explicitly unavailable, hidden, or mock with product-safe messaging.
  - Scope: meso, alternative data, rotation simulation, static chain surfaces.
  - Verify: contract tests assert non-real statuses.

- [x] T05: Add GSD bootstrap scripts for shell and PowerShell.
  - Files: `scripts/gsd-bootstrap.sh`, `scripts/gsd-bootstrap.ps1`.
  - Verify: dry-run/actual script creates expected directories and plan skeletons without requiring the GSD CLI.
