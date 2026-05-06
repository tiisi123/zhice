# T04 Summary: Wire ETF Read Path To Cache First

Status: ready for verification

## Change

- Moved ETF disk cache lookup before `TushareClient()` construction and token checks.
- A valid cached ETF bundle can now serve the ETF rotation read path even when `TUSHARE_TOKEN` is missing.
- Retains explicit sample fallback when neither cache nor live data is available.

## Verification

- Added `prototype/tests/features/test_etf_rotation_cache_priority.py`.
