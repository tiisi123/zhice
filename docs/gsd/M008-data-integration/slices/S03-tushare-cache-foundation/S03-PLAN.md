# S03 TuShare Cache Foundation

## Objective

Build cache-first TuShare ingestion inspired by zer0share-style batch sync.

## Tasks

- [x] T01: Add TuShare sync CLI skeleton under `packages/jobs`.
- [x] T02: Add cache helper for SQLite first, Parquet optional later.
- [x] T03: Add tests for cache hit, cache stale, and missing token.
- [x] T04: Wire ETF rotation read path to cache-first data.

## Verification

- `prototype/packages/jobs/tushare_sync.py`
- `prototype/packages/features/etf/cache.py`
- `prototype/tests/features/test_etf_cache.py`
- `prototype/tests/features/test_etf_rotation_cache_priority.py`
- `prototype/tests/jobs/test_tushare_sync.py`
