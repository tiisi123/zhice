# AGENTS.md

## Mission

This repository is a Chinese A-share AI research and strategy platform. Agents must work in small, reviewable slices and preserve production safety for market data, user auth, payments, and database state.

## Project Map

- `apps/api`: FastAPI backend.
- `apps/web`: React/Vite frontend.
- `apps/ai`: AI agents, prompts, LLM client, context builders.
- `packages/connectors`: external data sources.
- `packages/normalizers`: stock code, date, enum, and field normalization.
- `packages/features`: domain calculations and feature services.
- `packages/backtest`: strategy DSL and backtest engine.
- `docs/process`: collaboration, API, data source, review, and release rules.
- `scripts`: smoke, contract, source, and pre-PR checks.

## Required Reading

Before coding, read the relevant docs:

- `docs/process/01-协作规范.md`
- `docs/process/03-接口开发规范.md`
- `docs/process/04-数据源治理规范.md`
- `docs/process/07-代码评审清单.md`
- `docs/process/08-事故与回滚预案.md`

For shortline work, also read:

- `docs/短线作战接口映射清单.md`

For multi-agent planning, read:

- `docs/process/09-多Agent任务拆分与启动清单.md`

## Agent Roles

Use one role per task. Do not mix roles unless the issue explicitly says so.

| Role | Primary Scope |
| --- | --- |
| Architecture Integrator | API contracts, shared files, merge review, release notes |
| Shortline Backend | `apps/api/routes/intraday.py`, `replay.py`, `sentiment.py`, `theme.py`, `analysis.py`, `longhu.py`, `stock.py`, `packages/connectors/kpl`, `packages/features/market.py` |
| Shortline Frontend | `IntradayPage*`, `ReplayPage*`, `SentimentPage*`, `ThemePage`, `BrokenCasesPage`, `LonghuPage`, `useMarketWS` |
| Growth Value | growth, value, finance, ETF, valuation, research APIs and pages |
| User Commerce | auth, payment, watchlist, membership, dashboard, report archive |
| Engineering Quality | `scripts`, `docs/process`, `.github`, CI, deploy docs |

## Issue And PR Workflow

- Assign Codex work through `.github/ISSUE_TEMPLATE/agent_task.yml`.
- Each issue must name one role, allowed files, forbidden files, acceptance checks, and service dependencies.
- Keep default CI free of secrets, deployments, and realtime external market calls.
- Put API-contract, realtime-source, smoke, and other service-dependent checks in local verification or manual `workflow_dispatch`.
- PRs must use `.github/pull_request_template.md` and report files changed, checks run, skipped checks, and risks.

## Data Source Rules

- Shortline limit-up, broken-board, hot stocks, anomaly, and Longhu data must use KPL by default.
- Do not reintroduce XGT as a shortline default source.
- Do not silently fall back to mock data.
- Real-time market APIs must expose `source`, `data_status`, and `mock`.
- Prefer normalized internal fields such as `stock_code`, `stock_name`, `change_rate`, `turnover_ratio`, `board_count`, `first_plate_name`, and `related_plates`.

## File Ownership Rules

Avoid editing shared files unless the issue explicitly requires it:

- `apps/api/main.py`
- `apps/api/db.py`
- `apps/api/config.py`
- `apps/api/scheduler.py`
- `apps/api/ws_hub.py`
- `apps/web/src/App.tsx`
- `apps/web/src/layouts/AppLayout.tsx`
- `apps/web/src/api/client.ts`
- `packages/connectors/registry.py`
- `packages/shared/types.py`

If a task needs a shared file, call it out in the final response.

## Forbidden Changes

- Do not edit or commit `.env`.
- Do not edit or commit `data/*.db`, `data/*.db-wal`, or `data/*.db-shm`.
- Do not introduce `MOCK_*`, `mock: true`, or hidden demo data into production paths.
- Do not make unrelated refactors.
- Do not remove user changes unless explicitly requested.
- Do not change payment, auth, or database schema as a side effect of a market-data task.

## Check Commands

Default pre-PR check:

```powershell
python scripts/check_before_pr.py
```

With local API checks:

```powershell
python scripts/check_before_pr.py --api --api-base http://127.0.0.1:8000
```

With frontend checks:

```powershell
python scripts/check_before_pr.py --web
```

With Issue path limits:

```powershell
python scripts/check_before_pr.py --allow "docs/process/**" --allow "scripts/**" --deny "apps/**" --deny "packages/**" --deny "data/**" --deny ".env"
```

Full local verification when services are running:

```powershell
python scripts/check_before_pr.py --api --web --smoke
```

## Final Response Requirements

Every agent must report:

- Files changed.
- Checks run and results.
- Any skipped checks and why.
- Any risk that needs human review.
