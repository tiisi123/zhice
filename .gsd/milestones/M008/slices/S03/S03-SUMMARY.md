# S03 Summary: TuShare Cache Foundation

Status: completed

## Delivered

- Inspected existing TuShare connector paths, config names, retry behavior, and cache conventions.
- Enhanced ETF cache metadata helpers with hit/miss/stale semantics.
- Added a TuShare sync CLI skeleton with dry-run support.
- Changed ETF rotation live read path to prefer disk cache before constructing the TuShare client or checking token availability.

## Artifacts

- `docs/maintenance/M008-TUSHARE-CACHE-NOTES.md`
- `prototype/packages/features/etf/cache.py`
- `prototype/packages/features/etf/rotation.py`
- `prototype/packages/jobs/tushare_sync.py`
- `prototype/tests/features/test_etf_cache.py`
- `prototype/tests/features/test_etf_rotation_cache_priority.py`
- `prototype/tests/jobs/test_tushare_sync.py`

## Verification

- `cd prototype && python -m pytest tests/features/test_etf_cache.py tests/jobs/test_tushare_sync.py tests/features/test_etf_rotation_cache_priority.py -q`
- `python -m py_compile prototype\packages\features\etf\cache.py prototype\packages\features\etf\rotation.py prototype\packages\jobs\tushare_sync.py prototype\tests\features\test_etf_cache.py prototype\tests\features\test_etf_rotation_cache_priority.py prototype\tests\jobs\test_tushare_sync.py`
- `cd prototype && python -m packages.jobs.tushare_sync --table fund_daily --days 3 --dry-run`
- `git diff --check`

Result: S03 scoped tests passed with `6 passed`; dry-run printed a no-write plan for 13 ETF symbols.

## Residual Risk

- The CLI currently writes per-symbol JSON files for `fund_daily`; normalized table storage remains a later hardening step.
- ETF flow data still derives from amount/turnover proxy rather than official subscription/redemption data.
