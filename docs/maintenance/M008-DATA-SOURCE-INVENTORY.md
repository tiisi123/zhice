# M008 Data Source Inventory

Status: draft  
GSD: M008 / S02 / T01  
Source PRD: `docs/gsd-input/zhicev1-data-integration-prd.md`

## Purpose

This inventory is the backend source-of-truth map for removing silent mock/sample behavior and making zhiceV1 data contracts consistent. It records which routes use live data, cache, static data, explicit fallback, or mock/sample generators.

## Source Contract Baseline

Most API routes should use `wrap_contract(data, source, status, mock, message, ...)`.

Current contract fields:

- `source`
- `data_status`
- `mock`
- `message`
- `updated_at`

PRD target fields still need standardization:

- `data_source`
- `data_mode`
- `as_of`
- `status`
- `fallback_reason`

Compatibility recommendation for later tasks: keep current D004 fields, then add PRD fields as aliases/metadata so existing frontend code does not break.

## Connector Registry

| Connector | Factory | Source Type | Uses | Current Notes |
| --- | --- | --- | --- | --- |
| KPL | `get_kpl`, `get_kpl_realtime`, `get_kpl_history` | live upstream + Eastmoney-derived fallbacks | market replay, intraday, theme, stock, longhu, AI replay | Cookie/token dependent; sentinel helpers exist for explicit unavailable responses in several routes. |
| TuShare | `get_tushare` | live upstream + in-memory TTL cache | stock K-line, backtest, ETF, macro, valuation fallback, value screen | No durable batch cache yet; PRD S03 should add CLI/cache foundation. |
| DFCF | `get_dfcf` | live Eastmoney/DFCF endpoints | finance, valuation, growth portfolio, reports, expectations | Primary source for quote/financial/profile/announcements/reports. |
| XGT | `get_xgt` | live-ish public endpoint + in-memory cache | currently little/no route usage found | Keep as secondary candidate only after route usage is confirmed. |
| Eastmoney ETF | `get_etf` | live Eastmoney ETF kline endpoint | no active route usage found in scan | Potential duplicate with TuShare ETF path; decide in S03 whether to keep or remove. |

## Backend Route Inventory

| Area / Route Prefix | Representative Routes | Current Source Mode | Status |
| --- | --- | --- | --- |
| `/api/market` replay/intraday/sentiment | summary, ladder, sectors, limit-up, broken, hot-stocks, anomaly | KPL live; local JSON snapshots for summary/ladder/sentiment history | Mostly explicit. Sentinel fallback exists for KPL cookie/upstream failures in replay/intraday. |
| `/api/theme` | list, sectors, detail, cycle, cycle-batch | KPL live; `kpl_pool_derived`; local DB/cache for theme history | Mostly explicit. `plate_id.startswith("mock_")` returns empty, not mock. |
| `/api/stock` | detail, themes, pattern-match | KPL live for stock context; TuShare live for pattern match | Explicit unavailable if TuShare token missing for pattern match. Stock detail lacks KPL sentinel handling compared with theme/replay. |
| `/api/ai` | headline, replay-report, chat, agents | KPL + LLM for core chat/report; board-trading mixes KPL plus sample backtest; ETF agent forces sample engine | High-risk mixed mode. ETF agent and board-trading backtest use sample data while returning `status="real"` in some paths. |
| `/api/etf` | rotation dashboard, rotation-signals | TuShare live/cache/sample via ETF rotation feature | Uses `data_mode` mapping. Sample/hybrid is explicit, but sample fallback is still the default if live is unavailable. |
| `/api/backtest` | board-strategy, etf-rotation | mode defaults to `sample`; live uses KPL/TuShare when requested | Explicit `mock` for sample mode, but default sample conflicts with PRD target `data_mode=live` by default. |
| `/api/growth` | macro, prosperity, portfolio, meso, rotation | TuShare for macro/prosperity when configured; DFCF for portfolio; static/mock for meso/rotation | Macro/prosperity fallback is explicit; meso/rotation are static mock and in PRD scope. |
| `/api/value` | financial, screen, forecast, alternative, weekly-report | DFCF primary, TuShare fallback/screen; static sample for forecast/alternative/chain rules | Several mock/static rule paths are explicit. `macro-transmission` returns `status="real"` despite fixed rules, which needs product decision. |
| `/api/finance` | quote, summary, profile, announcements, research-reports, compare, explain PDF/report | DFCF primary; TuShare fallback for summary; user text/PDF + LLM | Mostly live/explicit. Compare assumes DFCF rows are real even when per-stock fields may be missing. |
| `/api/research` | announcements, alt-data, sellside, prosperity-cycle | sample/static research extension functions | Explicit mock, but entire route family is demo-like. Should be scoped, hidden, or wired to DFCF/TuShare equivalents. |
| `/api/chain` | list, detail, graph | static/sample chain registry | Currently returns `status="real"` for static/sample chain data. This is a contract inconsistency. |
| `/api/strategy` | templates, run, run-template, analyze | static strategy templates; TuShare-backed backtest engine | Templates are static but marked real. Backtest unavailable is explicit. |
| `/api/analysis` | broken-cases, event-chain, strategy-recommend | KPL/analysis rules; static chain registry fallback appears in event-chain | Needs deeper S02/T02/T04 review because static chain fallback may be presented as analysis. |

## Frontend Assumption Inventory

The frontend already has a useful D004 display foundation:

- `prototype/apps/web/src/api/useApiMeta.ts` normalizes `{source, data_status, mock, message}` into `ApiMeta`.
- `prototype/apps/web/src/components/DataStatusBadge.tsx` renders the six D004 states: `real`, `mock`, `fallback`, `unavailable`, `empty`, `error`.
- Pages such as `ReplayPageV2`, `IntradayPageV2`, `EtfRotationPage`, `ValuationPage`, `ThemeWorkshopPage`, `ProsperityPage`, `LonghuPage`, `AIAgentPage`, `BoardReplayPanel`, `BoardBacktestPanel`, and `EtfBacktestPanel` already consume this badge or `extractMeta`.

Frontend gaps and assumptions:

| Area / Component | Current Assumption | Risk |
| --- | --- | --- |
| `AIAgentPage.tsx` | Displays the API envelope status correctly, but trusts backend status. | If backend returns sample analysis with `data_status=real`, the UI faithfully shows the wrong thing. Backend contract is the blocker. |
| `BoardBacktestPanel.tsx` | Defaults to `mode="sample"` and labels it "演示数据". | Explicit but product-default sample conflicts with the PRD target of live/cache first. |
| `EtfBacktestPanel.tsx` | Defaults to `mode="sample"` and labels it "演示数据". | Same issue as board backtest; users see a complete chart before asking for live data. |
| `EtfRotationPage.tsx` | Defaults to `dataMode="auto"` and shows `DataStatusBadge` plus `data_mode`. | Good pattern to reuse for other analytical pages. |
| `ValueWorkshopPage.tsx` | Checks `status.data_status !== 'ok'`. | D004 status enum does not include `ok`; the alert appears for all real data and masks real degradation. |
| `ThemePage.tsx` / `StockPage.tsx` | Mostly check `mock?: boolean` via `MockBanner`. | They do not surface `fallback`, `unavailable`, or `empty` as clearly as `DataStatusBadge`. |
| `ChainPage.tsx` | Consumes static/sample chain endpoints without a prominent source badge. | Static chain registry can look like live industry graph data. |
| `ResearchPage.tsx` | Shows source/status in `Alert`, but not the unified badge. | Acceptable for now, but status vocabulary should be unified in S04. |
| Growth pages | Use a mix of `MockBanner`, local alerts, and nested data flags such as `data_source === 'mock'`. | Multiple display conventions make same-source pages feel inconsistent. |

Frontend priority fixes after this slice:

1. Backend-first: fix silent or misleading backend status before changing UI labels. Otherwise `DataStatusBadge` only amplifies bad metadata.
2. Replace `status.data_status !== 'ok'` checks with D004-aware checks (`fallback`, `unavailable`, `empty`, `error`, `mock`).
3. Move pages that only use `MockBanner` toward `DataStatusBadge` so `fallback/unavailable/empty` are visible.
4. Change backtest default mode from `sample` to `auto/live` only after backend live/cache behavior is durable enough not to create long loading or confusing empty states.

## Highest-Risk Silent Or Misleading Paths

1. `/api/ai/agent/etf-rotation`: calls `build_rotation_signals(mode="sample")` and `run_etf_backtest(mode="sample")`, sets `data_source="sample_engine+llm"`, then wraps with `status="real"`. This is the clearest silent demo risk.
2. `/api/ai/agent/board-trading`: live KPL context is mixed with `run_board_backtest(..., mode="sample")`; response status remains `real`, so the user cannot distinguish live evidence from sample backtest evidence.
3. `/api/chain/*`: `source="sample_chain"` but `status="real"`. Static chain registry should be `static` or `mock`, not real.
4. `/api/value/macro-transmission/{change}` and similar fixed-rule outputs: currently `status="real"` because the rule execution is real, but the data source is static rule logic. Needs a contract convention for deterministic static rules.
5. `/api/backtest/*`: default `mode="sample"` is explicit as mock, but PRD target says live/cache should be default; this is product-visible behavior.

## Existing Good Patterns To Reuse

- `apps.api.utils.contract.wrap_contract` enforces `mock=True` iff `data_status="mock"`.
- KPL sentinel helpers in replay/theme/intraday/top_traders turn cookie/upstream failures into `status="unavailable"` with an operator-action message.
- Valuation has removed `SAMPLE_FINANCIALS` fallback from `get_financial`; DFCF primary -> TuShare fallback -> unavailable is the right pattern.
- ETF rotation already carries `data_mode`, `data_source`, `coverage`, `fallback_count`, `as_of`, and `cache_stale`; S03 should generalize this.

## S04 Macro / Industry Route Map

Status: implemented for M008/S04.

Backend adapters:

| Function | File | Real Source | Explicit Fallback | Metadata |
| --- | --- | --- | --- | --- |
| `get_macro_indicators()` | `prototype/packages/features/macro/data.py` | TuShare `_post`: `cn_pmi`, `cn_cpi`, `cn_ppi`, `cn_m`, `sf_month` | `static_macro_sample` when TuShare unavailable/empty; `static_macro_reference` for LPR/CNY fields not covered by the adapter | Per item: `data_source`, `data_mode`, `as_of`, `fallback_reason` |
| `get_industry_prosperity()` | `prototype/packages/features/macro/data.py` | TuShare `_post`: `index_classify`, `sw_daily` | `static_industry_prosperity` when TuShare unavailable/empty | Per item: `data_source`, `data_mode`, `as_of`, `fallback_reason` |

API consumers:

| Route | File | Status Behavior |
| --- | --- | --- |
| `GET /api/growth/macro` | `prototype/apps/api/routes/growth.py` | live-only rows => `real`; live + static reference => `fallback`; all sample => `mock`; empty => `empty` |
| `GET /api/growth/prosperity` | `prototype/apps/api/routes/growth.py` | live TuShare industry rows => `real`; static matrix => `mock`; empty => `empty` |
| `GET /api/growth/prosperity/compare` | `prototype/apps/api/routes/growth.py` | same as prosperity, scoped to requested names |
| `GET /api/value/diffusion` | `prototype/apps/api/routes/value.py` | now detects real source by `data_mode="live"` instead of legacy `data_source=="tushare"` |
| `GET /api/value/turning-points` | `prototype/apps/api/routes/value.py` | same industry metadata detection |
| `GET /api/value/weekly-report` | `prototype/apps/api/routes/value.py` | same industry metadata detection before AI summary |

Frontend consumers:

| Component | File | S04 Change |
| --- | --- | --- |
| Growth workshop status alert | `prototype/apps/web/src/pages/GrowthWorkshopPage.tsx` | Uses `extractMeta` + `DataStatusBadge` for macro/prosperity statuses |
| Value workshop quality/valuation cards | `prototype/apps/web/src/pages/ValueWorkshopPage.tsx` | Replaced invalid `data_status !== "ok"` checks with D004-aware degraded status handling |

## Proposed Metadata Contract

Minimum top-level contract:

- Keep D004 fields for compatibility: `source`, `data_status`, `mock`, `message`, `updated_at`.
- Add PRD aliases/metadata where the route has them: `data_source`, `data_mode`, `as_of`, `fallback_reason`.
- For nested AI/analysis responses, include an `evidence` object with per-input metadata so a mixed live/sample answer does not look fully real.

Field mapping:

| PRD Field | Existing Field | Meaning | Compatibility Rule |
| --- | --- | --- | --- |
| `data_source` | `source` | Provider namespace, for example `kpl`, `tushare_fund_daily`, `sample_engine`, or combined AI sources. | Keep `source` as the frontend SSOT until all pages understand `data_source`; include both on new/changed routes. |
| `data_mode` | derived from `data_status` or feature payload | `live`, `cache`, `hybrid`, `static`, `sample`, `unavailable`. | Do not invent `ok/stale/partial`; map into the D004 six-state status at the envelope. |
| `as_of` | route-specific date fields / `updated_at` | Business date of the underlying data, not response generation time. | Use provider date when available; otherwise omit instead of copying `updated_at`. |
| `status` | `data_status` | PRD synonym for envelope state. | Avoid adding a second top-level `status` until clients are migrated; D004 `data_status` remains authoritative. |
| `fallback_reason` | `message` | Machine/ops friendly reason for degraded data. | Keep user-facing `message`; add `fallback_reason` only when the route can distinguish reason codes. |

Scenario mapping:

| Scenario | `data_status` | `mock` | `source` | PRD Metadata |
| --- | --- | --- | --- | --- |
| live provider success | `real` | `false` | provider namespace | `data_mode="live"`, `data_source=<provider>`, `as_of=<provider date>` |
| durable cache hit | `real` or `fallback` | `false` | provider cache namespace | `data_mode="cache"`, `cache_stale=false`, `as_of=<cached date>` |
| stale cache fallback | `fallback` | `false` | provider cache namespace | `data_mode="cache"`, `cache_stale=true`, `fallback_reason=<reason>` |
| static reference/rule | `fallback` or new explicit static alias | `false` | `static_*` / `*_rule` | `data_mode="static"`, `fallback_reason` when replacing live data |
| generated sample/demo | `mock` | `true` | `sample_*` / `mock_*` | `data_mode="sample"`, user-visible message required |
| no usable data | `unavailable` or `empty` | `false` | intended provider | `fallback_reason` for unavailable; no fabricated rows |

Combined AI response rule:

- All evidence live/cache and no missing required context: envelope `data_status="real"`.
- Mixed live/cache/static/sample evidence: envelope `data_status="fallback"`, `mock=false`, and `evidence` must show which inputs were degraded.
- All core evidence sample/demo: envelope `data_status="mock"`, `mock=true`, and the UI must show "演示数据".
- LLM failure with rule/template answer: envelope `data_status="fallback"` if the answer is still useful, or `unavailable` if no usable answer exists.

## S02/T04 Implemented Patch

Patched `/api/ai/agent/etf-rotation` first:

- Requests `build_rotation_signals(mode="auto")` and `run_etf_backtest(mode="auto")`.
- Derives response status from the returned `data_mode` values.
- If both core ETF evidence inputs are sample, returns `data_status="mock"` and `mock=true`.
- If evidence is mixed live/cache/sample/unavailable, returns `data_status="fallback"` and `mock=false`.
- Includes `data_source`, `data_mode`, `as_of`, `fallback_reason`, and per-input `evidence` metadata for signals and backtest.
- Focused test: `prototype/tests/api/test_ai_etf_agent_contract.py`.

## Verification Notes

- Command used for initial scan: `rg -n "mock|sample|demo|fallback|static|tushare|TuShare|dfcf|eastmoney|akshare|data_source|data_mode|as_of|cache|random|TODO" prototype/apps/api prototype/packages -S`
- GSD state after importing projection: `gsd-recover: recovered 1M/5S/21T hierarchy`
- Active task at creation: M008/S02/T01.
