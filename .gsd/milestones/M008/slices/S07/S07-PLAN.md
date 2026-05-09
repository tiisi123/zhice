# S07 Data Regression QA And KPL Detail Recovery Plan

## Objective

Stabilize the product after realtime data-source regressions by preserving the Eastmoney quote rollback, fixing the KPL sector detail/member contradiction, and adding a repeatable QA matrix for missing data and wrong status logic.

## Current QA Findings

- Rollback guard passed: no `eastmoney_quote`, Eastmoney quote helper, or related single-stock realtime fallback references were found under `prototype`.
- Focused regression tests passed: KPL connector, stock-any-code contract, theme fallback, replay sector members, ladder relay, and AI env isolation.
- Live/TestClient API matrix showed real KPL data for limit-up, broken-board, sector ranking, theme list, theme sectors, longhu rank, value screen, growth prosperity, ETF rotation, and AI headline.
- Confirmed P0 bug: `/api/theme/sectors` returned 30 real sectors, but the first five `/api/theme/sectors/{PlateID}` detail checks returned `unavailable` with count 0 because `ZhiShuStockList_W8` returned empty bodies.
- Confirmed UX/data-state risk: several page-backed routes return 401 without D004 metadata when unauthenticated, and current frontend patterns can collapse those failures into empty panels.
- Confirmed expected but user-facing unavailable state: `/api/backtest/board-strategy` defaults to live/auto and returns unavailable instead of silently using sample data when KPL live data is unavailable.

## Tasks

- [x] T01: Preserve rollback baseline and record verification.
  - Evidence: focused pytest suite passed; typecheck previously passed; no Eastmoney quote path grep hits.
  - Guard: do not reintroduce Eastmoney single-stock realtime in S07.

- [x] T02: Add deterministic regression test for theme sector detail fallback.
  - Stub KPL sector list/detail/limit-up pool so sector list has a PlateID and the detail endpoint is unavailable/empty.
  - Assert route returns fallback-derived member stocks from KPL limit-up pool with accurate source/status/message.

- [x] T03: Fix theme sector detail fallback.
  - If primary `get_concept_detail(plate_id)` is empty/unavailable, resolve sector name from current sector list and derive members from `_build_sectors_from_kpl_pool`.
  - Keep D004 semantics explicit: primary detail unavailable, fallback data derived from KPL event pool.
  - Live check: `/api/theme/sectors` now returns `kpl_mixed`; top `kpl_pool_*` rows open to real member counts from KPL limit-up pool.

- [x] T04: Add auth/data-state QA coverage.
  - Cover unauthenticated 401 responses separately from D004 data responses.
  - Add frontend helper tests or API client tests so 401 is not converted into `empty` business data.
  - Evidence: `extractErrorMeta` maps 401/403 to `source=auth,data_status=error`; Replay/Intraday V2 preserve error meta in status strips.

- [x] T05: Add API QA matrix script or test fixture.
  - Cover replay, intraday, theme, stock, longhu, value, growth, ETF, backtest, and AI endpoints.
  - Output route, HTTP status, source, data_status, mock, count, and message.
  - Mark route parameters and auth-required routes explicitly to avoid false positives.
  - Evidence: `prototype/scripts/qa_data_matrix.py` reports 32 routes, 0 failed (25 D004, 6 auth_required, 1 control).

- [x] T06: Browser smoke pass.
  - Run API + web locally and verify replay, intraday, theme workshop, stock detail, value workshop, strategy/backtest, verification/longhu, and AI surfaces.
  - Capture remaining no-data or wrong-status defects into this plan before closure.
  - Evidence: `npx playwright test e2e/s07-data-smoke.spec.ts --project=chromium` passed with system Chrome.

## Verification Commands

```powershell
cd prototype
python -m pytest tests/connectors/test_kpl_client.py tests/api/test_stock_any_code_contract.py tests/api/test_theme_fallback_contract.py tests/api/test_replay_sector_members.py tests/api/test_ladder_relay_route.py tests/ai/test_llm_client_env_isolation.py -q
```

```powershell
cd prototype/apps/web
npm run typecheck
```

```powershell
cd prototype
rg -n "eastmoney_quote|东财 quote|东财实时|_em_secid|_em_quote_price|_em_amount" .
```

## Closure Criteria

- Theme sector detail no longer reproduces “sector list has data but selected sector has no members” for fallback-covered sectors.
- QA matrix has no unexpected 500 and no unclassified missing-data state.
- UI no longer treats auth-required failures as business empty data.
- Focused backend tests and web typecheck pass.

## Final Verification

- `python -m pytest tests/connectors/test_kpl_client.py tests/api/test_stock_any_code_contract.py tests/api/test_theme_fallback_contract.py tests/api/test_theme_sector_detail_fallback.py tests/api/test_replay_sector_members.py tests/api/test_ladder_relay_route.py tests/ai/test_llm_client_env_isolation.py tests/scripts/test_qa_data_matrix.py -q`: passed, 38 tests.
- `npm run test -- useApiMeta.test.ts IntradayPageV2.test.tsx ReplayPageV2.test.tsx`: passed.
- `npm run typecheck`: passed.
- `python scripts/qa_data_matrix.py`: passed, 32 total / 0 failed.
- `npx playwright test e2e/s07-data-smoke.spec.ts --project=chromium`: passed, 3 total / 0 failed.
- Rollback guard grep for Eastmoney single-stock realtime helpers returned no hits.
