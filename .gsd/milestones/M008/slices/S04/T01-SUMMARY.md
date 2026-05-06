# T01 Summary: Locate Macro And Industry Routes

Completed: 2026-05-06

## Route Map

- `GET /api/growth/macro` -> `prototype/apps/api/routes/growth.py` -> `get_macro_indicators()`.
- `GET /api/growth/prosperity` -> `prototype/apps/api/routes/growth.py` -> `get_industry_prosperity()`.
- `GET /api/growth/prosperity/compare` -> `prototype/apps/api/routes/growth.py` -> `compare_industries()` -> `get_industry_prosperity()`.
- `GET /api/value/diffusion` -> `prototype/apps/api/routes/value.py` -> `get_industry_prosperity()`.
- `GET /api/value/turning-points` -> `prototype/apps/api/routes/value.py` -> `get_industry_prosperity()`.
- `GET /api/value/weekly-report` -> `prototype/apps/api/routes/value.py` -> `get_industry_prosperity()` + LLM summary.

## Frontend Consumers

- `prototype/apps/web/src/pages/GrowthWorkshopPage.tsx`.
- `prototype/apps/web/src/pages/ProsperityPage.tsx`.
- `prototype/apps/web/src/pages/ValueWorkshopPage.tsx`.

## Inventory

The route map was added to `docs/maintenance/M008-DATA-SOURCE-INVENTORY.md`.
