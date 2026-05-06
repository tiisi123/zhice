# S02 Plan: Source Inventory And No Silent Mock

## Objective

Inventory every major data path and convert silent mock/sample/demo behavior into explicit source metadata, fallback status, or product-scoped unavailability.

## Tasks

- [x] **T01: Inventory backend data providers** `est:45m`
  - Why: A single source map is needed before changing behavior safely.
  - Files: `prototype/apps/api`, `prototype/packages`
  - Do: classify providers as live, cache, static, fallback, sample, or mock.
  - Verify: write findings to `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md`.

- [x] **T02: Inventory frontend assumptions** `est:35m`
  - Why: UI copy and data badges must match API data reality.
  - Files: `prototype/apps/web/src`
  - Do: find sample labels, demo responses, hardcoded market data, and missing fallback states.
  - Verify: add frontend findings to the inventory document.

- [x] **T03: Define response metadata contract** `est:30m`
  - Why: API consistency needs one minimum field contract.
  - Files: `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md`
  - Do: define `data_source`, `data_mode`, `as_of`, `status`, `fallback_reason`.
  - Verify: contract has examples for live, cache, static, fallback, unavailable.

- [x] **T04: Patch one highest-risk silent mock path** `est:45m`
  - Why: The slice should produce a concrete behavior improvement, not only documentation.
  - Files: selected after T01/T02.
  - Do: replace silent mock with explicit fallback/unavailable metadata and user-facing copy.
  - Verify: focused test or API check proves the metadata is present.
