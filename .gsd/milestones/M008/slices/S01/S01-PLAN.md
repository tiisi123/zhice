# S01 Plan: P0 Data Unit Guardrails

## Objective

Fix visible data unit defects and prevent recurrence through API and UI tests.

## Tasks

- [x] **T01: Fix BoardReplayPanel change_rate display** `est:20m`
  - Why: API already returns percentage points for common cases, so multiplying by 100 can show impossible `1000%+` values.
  - Files: `prototype/apps/web/src/components/BoardReplayPanel.tsx`
  - Verify: frontend regression shows `10.00%`, not `1000.00%`.

- [x] **T02: Normalize board replay API change_rate values** `est:30m`
  - Why: API should tolerate ratio and percentage-point inputs consistently.
  - Files: `prototype/packages/normalizers/market_fields.py`, board replay route.
  - Verify: backend regression covers ratio and percentage-point inputs.

- [x] **T03: Add focused frontend regression** `est:20m`
  - Files: `prototype/apps/web/src/__tests__/BoardReplayPanel.test.tsx`
  - Verify: `npm run test -- BoardReplayPanel`.

- [x] **T04: Add focused backend regression** `est:20m`
  - Files: `prototype/tests/api/test_board_replay_route.py`
  - Verify: `pytest tests/api/test_board_replay_route.py`.

- [x] **T05: Record verification result in slice summary** `est:10m`
  - Files: `.gsd/milestones/M008/slices/S01/S01-SUMMARY.md`
  - Verify: summary lists commands already run and current residual risk.
