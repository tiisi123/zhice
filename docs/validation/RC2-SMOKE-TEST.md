# v0.1.0-rc2 External Smoke Test — Validation Evidence

**Date:** 2026-05-06
**Public URL:** `http://121.199.79.169:3001`
**Branch:** `release/v0.1.0-rc1`
**Tester:** Agent (curl/API checks)

## Infrastructure

| Component | Bind Address | External Access |
|-----------|-------------|-----------------|
| Vite frontend | `0.0.0.0:3001` | Direct — public IP reachable |
| FastAPI backend | `127.0.0.1:8000` | Via Vite proxy `/api/*` only |

## Smoke Test Results

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | Login page loads from public URL | **PASS** | HTML 200, SPA entry point (`/src/main.tsx`) present |
| 2 | Login works | **PASS** | POST `/api/auth/login` → 200, JWT issued, user=管理员 |
| 3 | Authenticated dashboard opens | **PASS** | GET `/api/auth/me` → 200, user profile + quota returned |
| 4 | `/api/health` via proxy | **PASS** | 200, database: ok, five_xx_recent: 0, alembic: 0005 |
| 5 | Replay page opens | **PASS** | `/api/market/ladder` → 200 (data_status=real, source=kpl) |
| 6 | AI Agent page opens | **PASS** | `/api/ai/agent/board-trading` → 200, `/api/ai/headline` → 200 |
| 7 | Event chain page opens | **PASS** | `/api/analysis/event-chain` → 200 with D004 contract |
| 8 | ETF rotation page opens | **PASS** | `/api/etf/rotation/dashboard` + `/api/backtest/etf-rotation` → 200 |
| 9 | Strategy/backtest page opens | **PASS** | `/api/strategy/templates` + `/api/backtest/board-strategy` → 200 |
| 10 | No 5xx errors | **PASS** | five_xx_recent=0, no server errors observed |

**Result: 10/10 PASS — No release blockers.**

## Additional Endpoints Verified

- `/api/market/limit-up` → 200
- `/api/market/hot-stocks` → 200
- `/api/market/sectors` → 200
- `/api/value/diffusion` → 200
- `/api/value/screen` → 200

## SPA Route Verification

All frontend paths return 200 HTML: `/`, `/replay`, `/event-chain`, `/etf-rotation`, `/growth-workshop`, `/backtest`

## Non-Blocking Notes

1. **Dev server in use** — Vite dev server, not production build. Acceptable for temporary RC testing only.
2. **No TLS** — plaintext HTTP. Fine for temporary RC testing, not for production.
3. **Backend localhost-only** — `127.0.0.1:8000` proxied through Vite. No direct external backend exposure.
4. **Manual browser verification recommended** — React rendering, chart components, and interactive behaviors not verified via curl. User should manually check charts, form interactions, and WebSocket features.

## Verdict

**v0.1.0-rc2 is acceptable for temporary external RC testing.**

All 10 automated smoke items pass. No P0/P1 blockers. Manual browser verification of rendering/charts/interactions is still recommended.
