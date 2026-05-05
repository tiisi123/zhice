# Changelog

## v0.1.0-rc1 (2026-05-06)

First release candidate — feature-complete MVP for internal trial use.

### Milestones Delivered

#### M001: 上线骨架 (Deployment Foundation)
- 4-service Docker Compose stack: MySQL 8.0, FastAPI/gunicorn, Nginx SPA, Caddy auto-HTTPS
- 27-table SQLAlchemy 2.x ORM + Alembic migration chain (0001–0005)
- Startup validation: ZHICE_JWT_SECRET, ZHICE_ADMIN_PASSWORD, DATABASE_URL, ENCRYPTION_KEY
- D004 data contract: `wrap_contract()` enforces source/status/mock fields on all 28 API routes
- DataStatusBadge 4-state component consumed by 10+ data pages
- `useApiMeta` hook for frontend contract compliance
- CI pipeline: lint (0-error gate), typecheck, api_contract, no_mock, Playwright E2E, 3-round smoke test
- Auto-deploy to staging on push:main via GitHub Actions

#### M002: 5xx 告警 + 邮件通知
- Thread-safe 5xx sliding-window counter with surge alerting
- SMTP notification templates (Chinese failure/recovery emails)
- APScheduler dual 30-min health check triggers

#### M003: AI 投研 (AI Research Engine)
- 6 AI agent types: IndustryProsperityAgent, TopTradersAgent, EventChainAgent, EtfRotationAgent, BoardTradingAgent, StockResearchAgent
- 7 feature functions: industry prosperity, top traders, event chain, ETF rotation signals, board/ETF backtest
- Deterministic strategy engine: no random.* usage, sorted stock universe, reproducible equity curves
- 6 acceptance verification scripts validating R006–R012

#### M004: 前端分析面板 (Frontend Analysis Panels)
- Board replay + top traders panels
- Event chain page with keyword search
- ETF rotation backtest tab
- Board backtest panel
- AI Agent page with dual data-context panels
- Full M004 acceptance verification script

#### M007: 质量加固 (Quality Hardening) — S01–S03
- S01: Vitest + React Testing Library test foundation (22 unit tests)
- S02: ESLint warning cleanup (40 → 0 warnings across 31 files)
- S03: Playwright E2E expansion (28 tests: auth navigation + business flows with mocked API)

### Infrastructure
- KPL connector: realtime/history client split, 7-parameter alignment with daban_pc
- Admin backend: invite codes, KPL cookie management, health monitoring panel
- Commercial gates: PaywallModal, useRequireVip, RegisterTermsModal, PaymentTermsModal, CheckoutPage
- AI compliance: AIBadge + AIDisclaimer on 28 pages
- Navigation restructured: 5+1 sidebar groups
- Battle flow cards (5-step tactical flow visualization)

### Architecture Decisions
- Single 4C8G host, no K8s (M001 scope)
- Single FastAPI worker (in-memory rate-limit/cache, no Redis)
- MySQL 8.0 + utf8mb4_0900_ai_ci + UTC
- Progressive planning (ADR-011) for multi-slice milestones
- Mock payment only — no real payment integration until commercial launch

### Known Limitations
- M007/S04–S06 deferred (bundle optimization, error boundaries, full quality closure)
- Payment gateway is mock-only (CheckoutPage exists but no real transaction processing)
- KPL cookie requires manual restart after admin update (lru_cache not auto-cleared)
- TuShare fina_indicator requires per-stock calls (no batch mode)
- ICP beian required for mainland China deployment (7–20 business days)
