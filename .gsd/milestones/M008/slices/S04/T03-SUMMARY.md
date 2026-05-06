# T03 Summary: Industry Real-Data Adapter Path

Completed: 2026-05-06

## Implemented

- Industry prosperity rows from TuShare `index_classify` + `sw_daily` now carry `data_source="tushare_sw_daily"`, `data_mode="live"`, `as_of`, and `fallback_reason`.
- Static industry matrix fallback is explicit `data_source="static_industry_prosperity"` and `data_mode="sample"`.
- `GET /api/growth/prosperity` and `/api/growth/prosperity/compare` expose top-level `data_source`, `data_mode`, `as_of`, and `fallback_reason`.
- Value routes that depend on industry prosperity now detect live data through `data_mode="live"`.

## Verification

- `python -m pytest tests/features/test_macro_real_data_contract.py tests/api/test_growth_macro_contract.py -q`
