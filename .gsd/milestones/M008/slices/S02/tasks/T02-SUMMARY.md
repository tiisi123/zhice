# T02 Summary: Inventory Frontend Assumptions

Status: ready for verification

## Findings

- Frontend has a reusable D004 base: `useApiMeta` plus `DataStatusBadge`.
- Several pages already show source/status consistently, especially replay, intraday v2, ETF rotation, valuation, theme workshop, prosperity, longhu, and AI agent pages.
- The highest frontend risk is not rendering logic; it is trusting incorrect backend metadata. `AIAgentPage` will show whatever status the backend reports.
- Backtest panels default to explicit `sample` mode. This is honest UI copy, but not aligned with the PRD target of live/cache first.
- Some pages only check `mock` and miss `fallback`, `unavailable`, and `empty`.
- `ValueWorkshopPage` compares `data_status !== 'ok'`, but the D004 enum has no `ok`.

## Artifact

- Updated `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md` with the frontend inventory and priority follow-ups.
