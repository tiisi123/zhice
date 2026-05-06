# M008 Context

## Source Inputs

- `docs/gsd-input/zhicev1-data-integration-prd.md`
- `docs/maintenance/M008-DATA-INTEGRATION-AUDIT.md`
- Existing mirror docs under `docs/gsd/M008-data-integration/`

## Operating Constraints

- Do not edit `release/v0.1.0-rc1` directly.
- Keep secrets out of git; provider tokens remain in local `.env` files.
- Avoid silent mock/demo analysis in user-facing AI or data APIs.
- Preserve unrelated worktree changes in runtime data, DB files, and ETF work-in-progress files.
- Prefer small verified slices and focused tests.

## Current Local Finding

- `gsd-pi@2.80.0` is installed and available as `gsd`.
- `gsd headless --timeout 60000 query --output-format json` runs in this repository.
- Older scripts that used `gsd doctor` / `gsd recover` have been updated to `gsd headless query` / `gsd headless recover`.
