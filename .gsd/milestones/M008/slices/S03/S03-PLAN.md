# S03 Plan: TuShare Cache Foundation

## Objective

Add the first reusable TuShare bulk sync and local cache foundation, following the PRD's zer0share-inspired offline-first pattern.

## Tasks

- [x] **T01: Inspect existing TuShare connector paths** `est:35m`
  - Files: `prototype/packages`, `prototype/apps/api`
  - Do: identify existing TuShare env vars, client helpers, retry behavior, and cache conventions.
  - Verify: findings added to implementation notes.

- [x] **T02: Add cache model and metadata helpers** `est:60m`
  - Files: `prototype/packages/features` or existing connector package.
  - Do: implement small read/write helper exposing `cache_hit_rate`, `as_of`, `cache_stale`, `data_source`.
  - Verify: unit tests cover hit, miss, stale.

- [x] **T03: Add TuShare sync CLI skeleton** `est:60m`
  - Files: `prototype/packages/jobs/tushare_sync.py` or nearest existing jobs package.
  - Do: support table, days, output, and dry-run options.
  - Verify: dry-run works without token; token path is documented but not committed.

- [x] **T04: Wire ETF read path to cache first** `est:90m`
  - Files: ETF rotation/cache modules and API route selected after inspection.
  - Do: prefer cache, then live fetch, then explicit fallback.
  - Verify: mock TuShare/cache tests cover priority order.
