# M008: zhiceV1 Data Integration

**Vision:** Unify zhiceV1 market data sources, remove silent mock/sample analysis, add field-level validation, and make the data integration work executable through GSD plan -> slice -> task flow.

**Success Criteria:**
- API responses for covered modules expose `data_source`, `data_mode`, and `as_of`.
- Mock/sample/static output appears only as explicit fallback with a user-visible reason.
- ETF, macro/industry, and valuation flows use real data paths or are explicitly scoped down.
- Business logic validation catches impossible percentage, missing field, and stale data cases.
- GSD preflight and recovery scripts run against the installed `gsd-pi` CLI.

---

## Slices

- [x] **S01: P0 Data Unit Guardrails** `risk:low` `depends:[]`
  > After this: board replay percentage values display as `10.00%`, not `1000.00%`, with frontend and backend regression coverage.

- [x] **S02: Source Inventory And No Silent Mock** `risk:medium` `depends:[S01]`
  > After this: every major data path is classified as live/cache/static/fallback/mock, with silent demo paths turned into explicit unavailable/fallback behavior.

- [x] **S03: TuShare Cache Foundation** `risk:high` `depends:[S02]`
  > After this: ETF/TuShare bulk sync and cache metadata exist behind a small CLI and reusable cache module.

- [x] **S04: Macro Industry Real Data** `risk:high` `depends:[S02,S03]`
  > After this: macro and industry endpoints prefer real TuShare/DFCF sources and expose freshness/source metadata.

- [x] **S05: GSD Automation Bootstrap** `risk:low` `depends:[]`
  > After this: the installed `gsd-pi` CLI is usable in this repository and preflight/recovery scripts call supported headless commands.

## Boundary Map

### S01 -> S02
Produces:
  prototype/packages/normalizers/market_fields.py -> market percentage normalization rules
  prototype/apps/web/src/__tests__/BoardReplayPanel.test.tsx -> UI regression for board replay percentage display
  prototype/tests/api/test_board_replay_route.py -> API regression for board replay change_rate inputs

Consumes: existing board replay API and UI display logic.

### S02 -> S03
Produces:
  data-source inventory document -> source classification and priority map
  no-silent-mock checklist -> endpoints and components requiring explicit fallback handling

Consumes from S01:
  market field normalization conventions.

### S03 -> S04
Produces:
  TuShare sync CLI -> cached ETF/fund/market tables
  cache module -> reusable cache hit/stale metadata

Consumes from S02:
  source inventory and target field metadata contract.

### S04 -> Acceptance
Produces:
  macro/industry real-data adapters
  endpoint contract tests for `data_source`, `data_mode`, `as_of`, and fallback reason

Consumes from S03:
  cache module and metadata conventions.
