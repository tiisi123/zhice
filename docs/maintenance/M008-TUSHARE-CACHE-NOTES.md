# M008 TuShare Cache Notes

Status: draft  
GSD: M008 / S03  
Source PRD: `docs/gsd-input/zhicev1-data-integration-prd.md`

## T01 Inventory

Existing TuShare configuration:

- Env/settings names: `TUSHARE_TOKEN`, `tushare_token`, `tushare_host`.
- Primary client: `prototype/packages/connectors/tushare/client.py`.
- Registry factory: `packages.connectors.registry.get_tushare()`.
- Token loading order: process env `TUSHARE_TOKEN`, then `apps.api.config.settings.tushare_token`, then `prototype/.env`.
- Client retry behavior: `_MAX_RETRIES = 2`, one linear backoff, returns previous in-memory result if present, otherwise empty list.
- Existing in-memory cache: per-client `_cache` with `_cache_ttl = 300.0`; key is api name, params hash, and fields.

Existing TuShare data methods:

- `get_daily`
- `get_fund_daily`
- `get_stock_basic`
- `get_daily_basic_latest`
- `get_fina_indicator_latest`
- `get_income_latest`
- `get_financial_summary`
- `get_daily_basic_all`
- `get_fina_indicator_all`

Current TuShare consumers:

- ETF rotation: `packages.features.etf.rotation` uses `TushareClient.get_fund_daily`.
- ETF backtest: `packages.features.backtest.etf_backtest` uses `get_tushare().get_fund_daily`.
- Stock pattern/K-line: `/api/stock/*` uses `get_tushare().get_daily`.
- Strategy/backtest engine: `packages.backtest.engine`.
- Finance/valuation/value/growth modules use stock basic, daily basic, financial summary, and industry/macro helpers.

Existing cache conventions:

- `prototype/packages/features/etf/cache.py` persists one ETF live-series bundle to `prototype/data/cache/etf_live_series.json`.
- Current file payload has `stored_at_ts`, `stored_at_iso`, `series`, and `meta`.
- `packages.features.etf.rotation` reads this cache, but currently creates `TushareClient()` and checks `client.configured` before loading the disk cache.
- That means "cache exists but token missing" incorrectly falls through to sample data.

S03 implementation direction:

1. Keep the existing ETF cache file and enhance it rather than creating a parallel cache.
2. Add metadata helpers that expose `cache_hit_rate`, `as_of`, `cache_stale`, `data_source`, and `cache_age_seconds`.
3. Move ETF live-series read path to cache-first, then live TuShare, then explicit sample fallback.
4. Add a small `packages/jobs/tushare_sync.py` CLI skeleton with dry-run support so later bulk sync can grow from a stable entrypoint.

## Residual Risks

- TuShare client uses an in-memory cache and a single JSON ETF cache file, not a normalized table store.
- `get_fina_indicator_all` notes that batch coverage is limited and may need per-stock fallback.
- ETF flow remains a volume/amount proxy, not real ETF share subscription/redemption flow.
