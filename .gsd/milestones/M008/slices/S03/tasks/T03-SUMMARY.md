# T03 Summary: Add TuShare Sync CLI Skeleton

Status: ready for verification

## Change

- Added `packages/jobs/tushare_sync.py`.
- Supports `--table`, `--days`, `--output`, and `--dry-run`.
- Initial supported table: `fund_daily`.
- Dry-run works without `TUSHARE_TOKEN` and writes no files.

## Verification

- Added `prototype/tests/jobs/test_tushare_sync.py`.
- Dry-run command: `python -m packages.jobs.tushare_sync --table fund_daily --days 3 --dry-run`.
