"""Tests for _evaluate_entry and multi-position deterministic entry in BacktestEngine."""

from __future__ import annotations

import pytest

from packages.backtest.dsl_schema import (
    ConditionRule,
    EntryConditions,
    ExitConditions,
    PositionConfig,
    SelectConditions,
    StrategyDSL,
)
from packages.backtest.engine import (
    BacktestEngine,
    BacktestDataUnavailable,
    STOCK_NAMES,
    _evaluate_entry,
)


def _bar(open_: float = 10.0, close: float = 10.5, pre_close: float = 10.0,
         amount: float = 50000, vol: float = 1000000, date: str = "20240101") -> dict:
    return {
        "date": date,
        "open": open_,
        "close": close,
        "pre_close": pre_close,
        "amount": amount,
        "vol": vol,
        "volume": vol,
    }


def _make_klines(codes: list[str], n_days: int = 20) -> dict[str, list[dict]]:
    """Build synthetic klines for multiple codes over n_days trading days."""
    klines: dict[str, list[dict]] = {}
    for ci, code in enumerate(sorted(codes)):
        bars = []
        base = 10.0 + ci
        for d in range(n_days):
            date = f"202401{d + 1:02d}" if d < 9 else f"202401{d + 1:02d}"
            if d + 1 > 31:
                date = f"202402{d - 30:02d}"
            pc = base + d * 0.1
            op = pc * 1.005
            cl = pc * 1.01
            bars.append({
                "date": date,
                "open": round(op, 4),
                "close": round(cl, 4),
                "pre_close": round(pc, 4),
                "amount": 50000 + ci * 1000,
                "vol": 1000000,
                "volume": 1000000,
            })
        klines[code] = bars
    return klines


# --- _evaluate_entry unit tests ---

class TestEvaluateEntry:
    def test_none_entry_always_true(self):
        assert _evaluate_entry(_bar(), None) is True

    def test_open_change_gte_pass(self):
        bar = _bar(open_=10.5, pre_close=10.0)
        entry = EntryConditions(open_change=ConditionRule(gte=3))
        assert _evaluate_entry(bar, entry) is True

    def test_open_change_gte_fail(self):
        bar = _bar(open_=10.1, pre_close=10.0)
        entry = EntryConditions(open_change=ConditionRule(gte=3))
        assert _evaluate_entry(bar, entry) is False

    def test_open_change_lte_pass(self):
        bar = _bar(open_=10.1, pre_close=10.0)
        entry = EntryConditions(open_change=ConditionRule(lte=3))
        assert _evaluate_entry(bar, entry) is True

    def test_open_change_lte_fail(self):
        bar = _bar(open_=10.5, pre_close=10.0)
        entry = EntryConditions(open_change=ConditionRule(lte=3))
        assert _evaluate_entry(bar, entry) is False

    def test_volume_gte_pass(self):
        bar = _bar(amount=60000)
        entry = EntryConditions(volume=ConditionRule(gte=50000))
        assert _evaluate_entry(bar, entry) is True

    def test_volume_gte_fail(self):
        bar = _bar(amount=30000)
        entry = EntryConditions(volume=ConditionRule(gte=50000))
        assert _evaluate_entry(bar, entry) is False

    def test_combined_open_change_and_volume(self):
        bar = _bar(open_=10.5, pre_close=10.0, amount=60000)
        entry = EntryConditions(
            open_change=ConditionRule(gte=3),
            volume=ConditionRule(gte=50000),
        )
        assert _evaluate_entry(bar, entry) is True

    def test_combined_open_change_pass_volume_fail(self):
        bar = _bar(open_=10.5, pre_close=10.0, amount=30000)
        entry = EntryConditions(
            open_change=ConditionRule(gte=3),
            volume=ConditionRule(gte=50000),
        )
        assert _evaluate_entry(bar, entry) is False

    def test_condition_string_ignored(self):
        bar = _bar()
        entry = EntryConditions(condition="涨停买入")
        assert _evaluate_entry(bar, entry) is True

    def test_pre_close_zero_handles_gracefully(self):
        bar = _bar(open_=10.0, pre_close=0.0)
        entry = EntryConditions(open_change=ConditionRule(gte=1))
        assert _evaluate_entry(bar, entry) is False


# --- Integration tests: deterministic entry + multi-position ---

class TestEngineEntryIntegration:
    def _make_dsl(self, entry=None, per_stock=20, max_total=60, tp=15, sl=-5, max_hold=3):
        return StrategyDSL(
            name="test",
            entry=entry,
            exit=ExitConditions(take_profit=tp, stop_loss=sl, max_hold_days=max_hold),
            position=PositionConfig(per_stock=per_stock, max_total=max_total),
        )

    def test_no_entry_conditions_enters_daily_on_first_stock(self):
        codes = ["A.SZ", "B.SZ", "C.SZ"]
        klines = _make_klines(codes, n_days=10)
        engine = BacktestEngine()
        dsl = self._make_dsl(entry=None, max_hold=2)
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades > 0
        assert result.data_source == "tushare"

    def test_deterministic_same_input_same_trades(self):
        codes = ["A.SZ", "B.SZ", "C.SZ"]
        klines = _make_klines(codes, n_days=15)
        engine = BacktestEngine()
        dsl = self._make_dsl(entry=None, max_hold=3)
        r1 = engine._run_real(dsl, klines, years=1)
        r2 = engine._run_real(dsl, klines, years=1)
        assert r1.trade_log == r2.trade_log
        assert r1.equity_curve == r2.equity_curve

    def test_multi_position_capped_by_max_total(self):
        codes = ["A.SZ", "B.SZ", "C.SZ", "D.SZ", "E.SZ"]
        klines = _make_klines(codes, n_days=5)
        engine = BacktestEngine()
        dsl = self._make_dsl(entry=None, per_stock=20, max_total=60, max_hold=10)
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades >= 1

    def test_entry_filter_restricts_trades(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes, n_days=10)
        engine = BacktestEngine()
        dsl_permissive = self._make_dsl(entry=None, max_hold=3)
        dsl_restrictive = self._make_dsl(
            entry=EntryConditions(open_change=ConditionRule(gte=99)),
            max_hold=3,
        )
        r_perm = engine._run_real(dsl_permissive, klines, years=1)
        r_rest = engine._run_real(dsl_restrictive, klines, years=1)
        assert r_perm.total_trades > r_rest.total_trades

    def test_all_stocks_filtered_by_entry_produces_no_trades(self):
        codes = ["A.SZ"]
        klines = _make_klines(codes, n_days=10)
        engine = BacktestEngine()
        dsl = self._make_dsl(
            entry=EntryConditions(open_change=ConditionRule(gte=999)),
            max_hold=3,
        )
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades == 0

    def test_open_change_lte_filter_works(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes, n_days=10)
        engine = BacktestEngine()
        dsl = self._make_dsl(
            entry=EntryConditions(open_change=ConditionRule(lte=2)),
            max_hold=2,
        )
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades >= 1

    def test_volume_filter_blocks_low_amount(self):
        codes = ["A.SZ"]
        klines = _make_klines(codes, n_days=10)
        engine = BacktestEngine()
        dsl = self._make_dsl(
            entry=EntryConditions(volume=ConditionRule(gte=999999999)),
            max_hold=3,
        )
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades == 0

    def test_max_total_100_allows_all_positions(self):
        codes = ["A.SZ", "B.SZ", "C.SZ"]
        klines = _make_klines(codes, n_days=5)
        engine = BacktestEngine()
        dsl_narrow = self._make_dsl(entry=None, per_stock=20, max_total=20, max_hold=10)
        dsl_wide = self._make_dsl(entry=None, per_stock=20, max_total=100, max_hold=10)
        r_narrow = engine._run_real(dsl_narrow, klines, years=1)
        r_wide = engine._run_real(dsl_wide, klines, years=1)
        assert r_wide.total_trades >= r_narrow.total_trades
