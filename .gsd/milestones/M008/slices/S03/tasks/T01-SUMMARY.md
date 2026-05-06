# T01 Summary: Inspect Existing TuShare Connector Paths

Status: completed

## Findings

- TuShare config already exists through `TUSHARE_TOKEN`, `tushare_token`, and `tushare_host`.
- `TushareClient` supports daily, fund daily, basic valuation, financial summary, and partial batch helpers.
- The connector has a 300-second in-memory cache and 2 retry attempts.
- ETF rotation already has a disk cache file via `packages.features.etf.cache`.
- ETF cache currently sits behind token configuration in `rotation.py`, so cache cannot help when token is missing.

## Artifact

- Added `docs/maintenance/M008-TUSHARE-CACHE-NOTES.md`.
