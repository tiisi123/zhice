# S07 PRD: Data Regression QA And KPL Detail Recovery

## Project Description

S07 stabilizes zhiceV1 after the attempted Eastmoney single-stock realtime integration. The product must return to a KPL-first short-line data model while preserving TuShare historical/basic analysis for any A-share. It also adds a QA-driven regression gate for the main product pages so missing data, wrong status labels, auth failures, and fallback behavior are visible and testable instead of being discovered manually in the UI.

## Why This Milestone

The user observed that adding Eastmoney realtime quote fallback made previously working KPL data paths become empty or logically wrong. The most urgent trust issue is not only whether an endpoint returns HTTP 200, but whether the page presents the right meaning: real data, empty event pool, unavailable upstream, stale cache, auth-required, or mock/sample output. S07 is needed to stop further data-source churn from breaking working product surfaces.

## User-Visible Outcome

Users can open the core pages and see either usable data or an accurate reason why a panel is unavailable. On the intraday and replay pages, KPL limit-up/broken/hot/sector data remains the first source. On stock detail, any A-share can still be analyzed with TuShare historical/basic data even when it is not in a KPL short-line event pool. On theme workshop, clicking a sector with visible strength or limit-up count shows member stocks or a clear fallback explanation, not a misleading empty detail panel.

## Completion Class

Integration plus operational verification. Unit tests are not enough because the failures involve live KPL behavior, auth/session behavior, UI metadata handling, and cross-endpoint consistency.

## Final Integrated Acceptance

1. Eastmoney single-stock realtime fallback is absent from the product stock realtime path; KPL remains the first and only realtime stock ranking path in this slice.
2. The API QA matrix covers replay, intraday, theme, stock detail, longhu, value, growth, ETF, backtest, and AI routes using HTTP/TestClient-style calls, not direct FastAPI function calls that mis-handle `Query` defaults.
3. A sector returned by the theme sector list with nonzero strength or limit-up evidence does not produce an unavailable/empty detail panel solely because the KPL sector detail endpoint returned an empty body.
4. Unauthenticated protected data endpoints are not rendered as “暂无数据” or generic “数据源不可用”; the user sees login/auth-required state where appropriate.
5. D004 metadata stays consistent: `mock=true` only with `data_status=mock`, real KPL/TuShare data is not marked as mock, real empty event pools are `empty`, and upstream failures are `unavailable` or `fallback` with a message.
6. Product AI API settings remain isolated from IDE AI API environment variables.

## Architectural Decisions

### Keep KPL First For Short-Line Realtime

KPL is the primary source for intraday short-line state, limit-up, broken-board, hot stock, sector strength, and short-line event pools. Eastmoney single-stock realtime quote is not reintroduced in S07.

Rationale: the attempted quote fallback changed the semantics of existing pages and created regressions. KPL event data and TuShare historical/basic data already define a cleaner separation.

Alternatives considered: keep Eastmoney quote as a secondary realtime source; rejected for S07 because it needs a separate interface and QA contract before it can be safely reintroduced.

### Treat Sector Detail Fallback As Derived KPL Data

When KPL sector ranking/list data exists but `ZhiShuStockList_W8` returns an empty body or sentinel, sector detail may derive members from the KPL limit-up pool by plate name and related plates.

Rationale: this fixes the user-visible contradiction where the product shows active sectors and 100 limit-up stocks but cannot show any members for a selected sector.

Alternatives considered: mark all sector details unavailable; rejected because it hides usable KPL event-pool evidence already present in the product.

### Separate Auth State From Data State

HTTP 401/403 responses are not data-empty states. Frontend code must preserve auth-required meaning instead of converting them to `empty`.

Rationale: users need to know whether to log in, configure data, or accept a genuine no-data result.

Alternatives considered: make all data endpoints public; left open per route because some endpoints may intentionally require VIP/auth.

## Error Handling Strategy

KPL upstream failures should produce explicit D004 responses with source, data status, mock flag, and message. If a primary KPL endpoint fails but another KPL endpoint can derive a useful view, the response should carry fallback/derived source metadata and explain the derivation. Auth failures should remain auth failures in UI state. Empty event pools should be shown as empty only when the upstream source responded successfully and the business event truly has no rows.

## Risks and Unknowns

KPL sector detail endpoint behavior may vary intraday and by date, including HTTP 200 with empty body. Some KPL routes depend on operator token/cookie freshness. TuShare availability depends on configured token and quota. Browser-level QA may require running both API and Vite servers with a clean session to reproduce auth/UI states.

## Existing Codebase / Prior Art

The KPL connector already has realtime/history clients, sentinel state, concept list fallback, and stock ranking normalization. Theme routes already derive theme lists from sectors and sectors from limit-up pools. D004 response contracts and `DataStatusBadge` provide a shared status vocabulary. Existing tests cover KPL client behavior, arbitrary stock analysis, theme fallback, replay sector members, ladder relay, and AI environment isolation.

## Relevant Requirements

This slice advances M008’s requirements to avoid silent mock/sample output, validate business logic, preserve real source metadata, and make data integration executable through GSD. It also responds to the newer product requirement that KPL remains the first realtime source and TuShare remains the historical/basic source for any A-share.

## Scope

In scope:
- Preserve the rollback of Eastmoney single-stock realtime quote fallback.
- QA audit of main product pages and their backing APIs.
- Fix theme sector detail/member contradiction.
- Fix auth-required versus empty/unavailable UI semantics.
- Add or update focused tests and QA scripts for these contracts.

Out of scope:
- Reintroducing Eastmoney single-stock quote fallback.
- Replacing KPL with another realtime market-wide source.
- Solving all live data provider quota/freshness issues.
- Redesigning page layout beyond status/error correctness.

Non-goals:
- Silent sample data substitution for unavailable live routes.
- Changing IDE AI API environment variables for product AI behavior.

## Technical Constraints

The implementation must respect the D004 status enum. Product AI configuration must use product-specific environment variables and never depend on generic IDE AI variables. FastAPI route tests should use explicit HTTP/TestClient calls for query defaults. Network-backed tests must be separated from deterministic contract tests or written with stubs.

## Integration Points

KPL realtime and history hosts provide short-line event, ranking, sector, and detail data. TuShare provides stock historical/basic/fundamental analysis. DFCF/Eastmoney remains valid for existing news/financial/report paths, but not as an S07 single-stock realtime quote fallback. The web app consumes D004 metadata through API client helpers and status badges.

## Testing Requirements

Tests must include deterministic unit/API tests for the sector detail fallback, stock-any-code contract, D004 metadata consistency, and auth/error meta extraction. QA scripts should record route, HTTP status, source, data_status, mock, count, and message for the main API matrix. Browser smoke should cover replay, intraday, theme workshop, stock detail, value workshop, strategy/backtest, longhu/verification, and AI surfaces when servers are running.

## Acceptance Criteria

- KPL rollback guard: no references to Eastmoney quote helpers or `eastmoney_quote` remain in the stock realtime path.
- API matrix: reviewed endpoints return either valid D004 data responses or explicit auth/control responses, with no unexpected 500.
- Theme detail: top KPL sectors with visible list data do not all collapse to unavailable detail; fallback-derived members are returned when limit-up pool evidence exists.
- Intraday/replay UI: protected route failures are not counted as zero business rows.
- Backtest UI: unavailable live data communicates that live data is unavailable and sample mode is opt-in.
- AI env isolation: product AI tests continue to prove generic IDE AI env vars do not configure product AI.

## Resolved Questions

- Protected endpoints remain protected in S07. The UI and QA matrix classify 401/403 as auth-required/error metadata instead of business-empty data.
- Sector detail derived from the KPL limit-up pool uses `data_status=fallback` and `source=kpl_pool_derived`, because the primary KPL detail endpoint failed or returned empty.
- S07 includes a Playwright browser smoke artifact: `prototype/apps/web/e2e/s07-data-smoke.spec.ts`.

## Open Questions

None for S07 closure.
