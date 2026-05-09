# S02 Source Inventory No Mock

## Objective

Inventory all mock/sample/static/fallback paths and classify whether to replace, label, or hide them.

## Tasks

- [x] T01: Generate source inventory from `rg "mock|sample|static|fallback|data_mode|data_source"`.
- [x] T02: Group findings by shortline, ETF, macro, growth, value, tools.
- [x] T03: Identify user-visible non-real outputs.
- [x] T04: Create replacement/hide/label decision table.

## Verification

- Inventory and decision table are recorded in `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md`.
