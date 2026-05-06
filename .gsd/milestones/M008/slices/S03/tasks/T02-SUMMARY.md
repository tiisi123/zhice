# T02 Summary: Add Cache Model And Metadata Helpers

Status: ready for verification

## Change

- Enhanced `packages.features.etf.cache` with metadata helpers.
- Added `describe_cache`.
- Added path injection for tests/CLI reuse.
- `load_cached_bundle` now returns metadata including `cache_hit_rate`, `as_of`, `cache_stale`, `data_source`, `cache_age_seconds`, and `cache_path`.

## Verification

- Added `prototype/tests/features/test_etf_cache.py`.
