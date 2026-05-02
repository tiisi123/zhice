"""Tests for ParameterOptimizer.grid_search and SimulatedTrader determinism."""

from __future__ import annotations

import math
import pytest

from packages.backtest.dsl_schema import (
    ConditionRule,
    EntryConditions,
    ExitConditions,
    PositionConfig,
    SelectConditions,
    StrategyDSL,
    STRATEGY_TEMPLATES,
)
from packages.backtest.engine import BacktestEngine, BacktestResult
from packages.backtest.optimizer import ParameterOptimizer, SimulatedTrader


def _make_klines(n_stocks: int = 3, n_days: int = 30) -> dict[str, list[dict]]:
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    klines: dict[str, list[dict]] = {}
    for ci, code in enumerate(sorted(codes)):
        base = 10.0 + ci * 5.0
        bars = []
        for d in range(n_days):
            month = 1 + d // 28
            day = 1 + d % 28
            date = f"2024{month:02d}{day:02d}"
            close = base * (1 + math.sin(d / 10) * 0.05)
            prev_close = base * (1 + math.sin((d - 1) / 10) * 0.05) if d > 0 else base
            open_price = (close + prev_close) / 2
            pct_chg = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
            bars.append({
                "date": date,
                "open": round(open_price, 4),
                "close": round(close, 4),
                "high": round(max(close, open_price) * 1.01, 4),
                "low": round(min(close, open_price) * 0.99, 4),
                "pre_close": round(prev_close, 4),
                "pct_chg": round(pct_chg, 4),
                "amount": 50000 + ci * 10000,
                "vol": 1000000 + ci * 100000,
                "volume": 1000000 + ci * 100000,
            })
        klines[code] = bars
    return klines


class TestGridSearchSorted:
    def test_results_sorted_by_sharpe_descending(self, monkeypatch):
        klines = _make_klines()

        def fake_run(self_engine, dsl, years=3):
            return self_engine._run_real(dsl, klines, years)

        monkeypatch.setattr(BacktestEngine, "run", fake_run)
        opt = ParameterOptimizer()
        base_dsl = StrategyDSL(
            name="test",
            exit=ExitConditions(take_profit=10, stop_loss=-5, max_hold_days=3),
            position=PositionConfig(per_stock=20, max_total=60),
        )
        results = opt.grid_search(
            base_dsl,
            take_profit_range=[5, 10],
            stop_loss_range=[-3, -5],
            hold_days_range=[1, 3],
        )
        sharpes = [r["sharpe_ratio"] for r in results]
        assert sharpes == sorted(sharpes, reverse=True)


class TestGridSearchSingleCombo:
    def test_single_param_combo_returns_one_result(self, monkeypatch):
        klines = _make_klines()

        def fake_run(self_engine, dsl, years=3):
            return self_engine._run_real(dsl, klines, years)

        monkeypatch.setattr(BacktestEngine, "run", fake_run)
        opt = ParameterOptimizer()
        base_dsl = StrategyDSL(
            name="single",
            exit=ExitConditions(take_profit=10, stop_loss=-5, max_hold_days=3),
        )
        results = opt.grid_search(
            base_dsl,
            take_profit_range=[10],
            stop_loss_range=[-5],
            hold_days_range=[3],
        )
        assert len(results) == 1


class TestGridSearchDeterministic:
    def test_same_dsl_same_klines_same_ranked_results(self, monkeypatch):
        klines = _make_klines()

        def fake_run(self_engine, dsl, years=3):
            return self_engine._run_real(dsl, klines, years)

        monkeypatch.setattr(BacktestEngine, "run", fake_run)
        opt = ParameterOptimizer()
        base_dsl = StrategyDSL(
            name="deterministic",
            exit=ExitConditions(take_profit=10, stop_loss=-5, max_hold_days=3),
            position=PositionConfig(per_stock=20, max_total=60),
        )
        params = dict(
            take_profit_range=[5, 10],
            stop_loss_range=[-3, -5],
            hold_days_range=[1, 3],
        )
        r1 = opt.grid_search(base_dsl, **params)
        r2 = opt.grid_search(base_dsl, **params)
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a["sharpe_ratio"] == b["sharpe_ratio"]
            assert a["total_return"] == b["total_return"]
            assert a["take_profit"] == b["take_profit"]
            assert a["stop_loss"] == b["stop_loss"]


class TestSimulatedTraderRoundTrip:
    def test_buy_sell_round_trip_preserves_capital(self):
        trader = SimulatedTrader(initial_capital=100_000)
        trader.buy("600519.SH", "贵州茅台", 100.0, 10_000)
        assert trader.capital < 100_000
        trader.sell("600519.SH", 100.0)
        assert trader.capital == 100_000

    def test_buy_insufficient_funds_raises(self):
        trader = SimulatedTrader(initial_capital=100)
        with pytest.raises(ValueError, match="资金不足"):
            trader.buy("600519.SH", "贵州茅台", 100.0, 200)

    def test_sell_nonexistent_position_raises(self):
        trader = SimulatedTrader(initial_capital=100_000)
        with pytest.raises(ValueError, match="无"):
            trader.sell("600519.SH", 100.0)


class TestSimulatedTraderNextDayDeterministic:
    def test_next_day_price_unchanged(self):
        trader = SimulatedTrader(initial_capital=100_000)
        trader.buy("600519.SH", "贵州茅台", 10.0, 10_000)
        price_before = trader.positions[0]["price"]
        trader.next_day()
        price_after = trader.positions[0]["price"]
        assert price_after == price_before

    def test_next_day_increments_day(self):
        trader = SimulatedTrader()
        assert trader.day == 0
        trader.next_day()
        assert trader.day == 1
        trader.next_day()
        assert trader.day == 2

    def test_status_consistent_after_next_day(self):
        trader = SimulatedTrader(initial_capital=100_000)
        trader.buy("600519.SH", "贵州茅台", 10.0, 50_000)
        trader.next_day()
        trader.next_day()
        status = trader.status()
        expected_total = trader.capital + sum(
            p["price"] * p["shares"] for p in trader.positions
        )
        assert status["total_value"] == round(expected_total, 2)


def _make_limit_up_klines(n_stocks: int = 3, n_days: int = 30, board_days: int = 4) -> dict[str, list[dict]]:
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    klines: dict[str, list[dict]] = {}
    for ci, code in enumerate(sorted(codes)):
        base = 10.0
        bars = []
        for d in range(n_days):
            month = 1 + d // 28
            day = 1 + d % 28
            date = f"2024{month:02d}{day:02d}"
            prev_close = base
            limit_up_days = board_days if ci == 0 else max(0, board_days - ci - 1)
            if d >= n_days - limit_up_days:
                close = prev_close * 1.10
            else:
                close = prev_close * 1.005
            open_price = (close + prev_close) / 2
            pct_chg = ((close - prev_close) / prev_close * 100)
            bars.append({
                "date": date,
                "open": round(open_price, 4),
                "close": round(close, 4),
                "high": round(close * 1.005, 4),
                "low": round(prev_close * 0.995, 4),
                "pre_close": round(prev_close, 4),
                "pct_chg": round(pct_chg, 4),
                "amount": 50000 + ci * 10000,
                "vol": 1000000,
                "volume": 1000000,
            })
            base = close
        klines[code] = bars
    return klines


class TestTemplateParsesAndRuns:
    def test_lianban_longtou_template_through_optimizer(self, monkeypatch):
        klines = _make_limit_up_klines(n_stocks=3, n_days=30, board_days=4)

        def fake_run(self_engine, dsl, years=3):
            return self_engine._run_real(dsl, klines, years)

        monkeypatch.setattr(BacktestEngine, "run", fake_run)
        opt = ParameterOptimizer()
        template = STRATEGY_TEMPLATES["连板龙头低吸"]
        results = opt.grid_search(
            template,
            take_profit_range=[10],
            stop_loss_range=[-5],
            hold_days_range=[3],
        )
        assert len(results) == 1
        assert "sharpe_ratio" in results[0]
        assert "total_return" in results[0]
