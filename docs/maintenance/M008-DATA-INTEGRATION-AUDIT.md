# M008 Data Integration Audit

Date: 2026-05-06
Branch: `polish/replay-copilot-context-clarity`
Input: `docs/gsd-input/zhicev1-data-integration-prd.md`

## Executive Summary

zhiceV1 已经具备短线、ETF、成长、价值、AI Copilot 等页面骨架，但数据层仍存在三类主要风险：

1. 同类行情字段口径未完全统一，例如 `change_rate` 在部分链路里被当作比例值、部分链路里被当作百分比点。
2. ETF/宏观/行业/部分成长价值模块仍存在 `sample/static/fallback` 数据路径，不能承诺生产级真实分析。
3. 当前环境缺少 `.gsd/` 目录且未安装 `gsd` CLI，不能直接运行 `gsd auto`；只能先补 durable plan/slice/task 文档与 preflight 脚本。

本轮已先修复截图中的 P0 问题：涨停复盘涨幅不再二次乘以 100。

## Architect Review

### Data Source Consistency

Short-line market data currently uses:

- 涨停/炸板池：Eastmoney public pool via `packages/connectors/kpl/client.py`
- 题材/概念强度：KPL `ConceptSelected` / `RealRankingInfo`
- 复盘聚合：`apps/api/routes/replay.py`, `apps/api/routes/board_replay.py`

Target principle:

- Same business concept, same normalized unit.
- Every route returns source metadata: `source`, `data_status`, `updated_at`, and later `data_source`, `data_mode`, `as_of`.
- LLM/Copilot must consume normalized evidence packages, not raw route fragments.

### TuShare Direction

The PRD direction is sound: follow the zer0share-style idea of batch sync first, realtime only as refill. The implementation should be:

- CLI job: `python -m packages.jobs.tushare_sync ...`
- Storage: SQLite first, Parquet optional later.
- Route read order: local cache -> live TuShare refresh -> unavailable/fallback status.
- Tests mock TuShare responses and validate cache hit/stale metadata.

### GSD Auto Readiness

Current blockers:

- `.gsd/` does not exist.
- `gsd` command is not installed in current shell.
- `scripts/gsd-preflight.sh` assumes both exist.

Recommendation:

- Add `.gsd/milestones/M008-data-integration/` durable artifacts.
- Add `make gsd-preflight` target.
- Do not claim `gsd auto` can run until CLI is installed.

## Product Review

Priority order:

1. P0: fix visible wrong market data, especially涨幅/涨跌幅/承接率.
2. P1: hide or label modules that still use sample/static data.
3. P1: expose source freshness in UI: source, as_of, cache hit/stale.
4. P2: AI Copilot answer must cite data evidence and refuse analysis when evidence is empty.

User-facing rule:

- If data is sample/static/unavailable, UI must say so plainly and avoid investment-style conclusions.

## QA Review

Required test suites:

- Unit: field normalization, `change_rate`, `pre_close=0`, empty provider response.
- Contract: no mock/sample on production-critical routes unless marked fallback/unavailable.
- Integration: ETF cache read path, TuShare sync path, macro latest two periods.
- UI regression: screenshot-level sanity for percentage displays.

Immediate tests added in this slice:

- `BoardReplayPanel` renders `10.00%`, not `1000.00%`.
- `_normalize_change_rate` keeps percentage points and converts ratio values.

## Slices

### S1 - P0 Data Unit Guardrails

- T01: Fix board replay `change_rate` UI unit.
- T02: Normalize board replay backend output.
- T03: Add regression tests.

### S2 - Data Source Inventory And Kill Mock

- T01: Inventory `mock/sample/static/fallback` code paths.
- T02: Classify by module and user visibility.
- T03: Hide or clearly label non-real routes.

### S3 - TuShare Batch Cache

- T01: Add TuShare sync CLI.
- T02: Add SQLite/Parquet cache helper.
- T03: Wire ETF rotation to cache-first reads.

### S4 - Macro/Industry Realization

- T01: Replace static macro arrays with TuShare/DFCF readers.
- T02: Add latest-two-period validation.
- T03: Add UI freshness metadata.

### S5 - GSD Automation Bootstrap

- T01: Add `.gsd` milestone/slice durable files.
- T02: Add `make gsd-preflight`.
- T03: Document local `gsd` CLI installation requirement.

## Acceptance

- No visible percentage field exceeds normal exchange limits without explicit anomaly label.
- All production-critical routes are real/cache/fallback/unavailable, never silent mock.
- `npm run lint`, `npm run typecheck`, `npm run test`, API unit tests pass.
- GSD preflight clearly reports missing CLI instead of failing opaquely.
