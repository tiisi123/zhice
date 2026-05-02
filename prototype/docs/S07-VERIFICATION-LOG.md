# S07 Verification Log

## Determinism Proof

Same DSL + same kline data produces identical backtest results across multiple runs.

**Test evidence:** `tests/backtest/test_engine_integration.py::TestReproducibility`
- `test_identical_dsl_identical_klines_same_result` — asserts trade_log, equity_curve, total_return, total_trades identical across 2 runs
- `test_reproducibility_with_all_dsl_fields` — full 5-field DSL (select + entry + exit + position + environment) produces identical results

**Runtime proof:**
```
Run1 trades: 12  return: 34.2997
Run2 trades: 12  return: 34.2997
trade_log identical: True
equity identical: True
DETERMINISTIC: True
```

## Select Sensitivity Proof

Changing `select.连板次数` threshold produces visibly different trade sets.

**Test evidence:** `tests/backtest/test_engine_integration.py::TestSelectSensitivity`
- `test_board_count_gte3_vs_gte1_different_trades` — strict (≥3) vs loose (≥1) produces different total_trades or different trade_log
- `test_board_count_gte99_empty_universe` — impossibly strict threshold yields zero trades

## Random Elimination Proof

Zero `random.*` usage in `packages/backtest/`:

```bash
$ grep -rn 'import random\|random\.' packages/backtest/ | grep -v __pycache__
# (no output — zero matches)
```

Changes made across S07:
- T01: Replaced `random.choice` stock sampling with deterministic modulo cycling
- T02: Replaced `random.choice` entry selection with DSL-driven open_change/volume evaluation
- T03: Added environment filter — no random elements
- T04: Removed `random.uniform` from `SimulatedTrader.next_day()`, eliminated `import random` from optimizer.py

## Test Suite Summary

Full test suite: **147 passed** in 1.12s

| Module | Tests | Status |
|--------|-------|--------|
| tests/backtest/test_engine_select.py | 14 | PASSED |
| tests/backtest/test_engine_entry.py | 20 | PASSED |
| tests/backtest/test_engine_integration.py | 23 | PASSED |
| tests/backtest/test_optimizer.py | 10 | PASSED |
| tests/connectors/test_kpl_client.py | 22 | PASSED |
| tests/api/test_admin_routes.py | 12 | PASSED |
| tests/api/test_rotation_sentinel.py | 6 | PASSED |
| tests/services/test_cookie_provider.py | 11 | PASSED |
| tests/services/test_kpl_health.py | 10 | PASSED |
| tests/notify/test_smtp.py | 8 | PASSED |
| **Total** | **147** | **ALL PASSED** |

### Backtest-specific coverage
- Select condition evaluation (gte/lte/eq operators, board_count, market_cap, is_leader, seal_amount)
- Entry signal filtering (open_change, volume thresholds)
- Exit parameters (take_profit, stop_loss, max_hold_days)
- Position management (per_stock cap, max_total enforcement)
- Environment filter (sentiment 5-tier scale, market_change)
- Optimizer grid search (deterministic, sorted by sharpe)
- SimulatedTrader (buy/sell round-trip, next_day deterministic)

## Lint/Build Baseline

### py_compile
All backtest modules compile without error:
- `packages/backtest/engine.py` — OK
- `packages/backtest/optimizer.py` — OK
- `packages/backtest/dsl_schema.py` — OK
- `apps/api/routes/strategy.py` — OK
- `apps/api/routes/advanced_strategy.py` — OK

### Contract scripts
- `scripts/check_api_contract.py` — compiles OK
- `scripts/smoke_test.py` — compiles OK
- `scripts/contract_endpoints.py` — compiles OK
- `scripts/check_no_mock.py` — PASSED

### Frontend build
- `npm run build` — SUCCESS (built in 1.31s)

### ESLint
- 0 errors, 47 warnings (matches S02/S03 baseline)
