# S04 Macro Industry Real Data

## Objective

Replace static macro/industry arrays with real TuShare/DFCF backed data and validation.

## Tasks

- [x] T01: Inventory current static macro/industry constants.
- [x] T02: Map each indicator to TuShare/DFCF source.
- [x] T03: Add latest-two-period completeness checks.
- [x] T04: Update route metadata with `data_source`, `data_mode`, `as_of`.

## Verification

- `python -m pytest tests/features/test_macro_real_data_contract.py tests/api/test_growth_macro_contract.py -q`
