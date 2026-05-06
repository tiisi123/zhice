# T02 Summary: Macro Real-Source Adapter Metadata

Completed: 2026-05-06

## Implemented

- Macro rows from TuShare now carry `data_source`, `data_mode="live"`, `as_of`, and `fallback_reason`.
- Static LPR and CNY reference rows are explicit `data_mode="static"` with `fallback_reason="indicator_not_available_in_current_tushare_adapter"`.
- Full macro fallback rows are explicit `data_mode="sample"` and `data_source="static_macro_sample"`.
- `GET /api/growth/macro` now reports `real`, `fallback`, `mock`, or `empty` based on row modes instead of guessing from legacy source strings.

## Verification

- `python -m pytest tests/features/test_macro_real_data_contract.py tests/api/test_growth_macro_contract.py -q`
