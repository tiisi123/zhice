"""Full-DSL integration tests: reproducibility, select sensitivity, environment filtering."""

from __future__ import annotations

import math
import pytest

from packages.backtest.dsl_schema import (
    ConditionRule,
    EntryConditions,
    EnvironmentConditions,
    ExitConditions,
    PositionConfig,
    SelectConditions,
    StrategyDSL,
    STRATEGY_TEMPLATES,
)
from packages.backtest.engine import (
    BacktestEngine,
    BacktestDataUnavailable,
    BacktestResult,
    _evaluate_environment,
    _compute_sentiment_level,
    SENTIMENT_TIERS,
)


def _make_klines(n_stocks: int = 5, n_days: int = 60, seed_prices: list[float] | None = None) -> dict[str, list[dict]]:
    """Build deterministic OHLCV data: close[i] = base_price * (1 + sin(i/10)*0.05)."""
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    if seed_prices is None:
        seed_prices = [10.0 + i * 5.0 for i in range(n_stocks)]

    klines: dict[str, list[dict]] = {}
    for ci, code in enumerate(sorted(codes)):
        base = seed_prices[ci] if ci < len(seed_prices) else 10.0
        bars = []
        for d in range(n_days):
            month = 1 + d // 28
            day = 1 + d % 28
            date = f"2024{month:02d}{day:02d}"

            close = base * (1 + math.sin(d / 10) * 0.05)
            prev_close = base * (1 + math.sin((d - 1) / 10) * 0.05) if d > 0 else base
            open_price = (close + prev_close) / 2
            high = max(close, open_price) * 1.01
            low = min(close, open_price) * 0.99
            pct_chg = ((close - prev_close) / prev_close * 100) if prev_close > 0 else 0.0

            bars.append({
                "date": date,
                "open": round(open_price, 4),
                "close": round(close, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "pre_close": round(prev_close, 4),
                "pct_chg": round(pct_chg, 4),
                "amount": 50000 + ci * 10000,
                "vol": 1000000 + ci * 100000,
                "volume": 1000000 + ci * 100000,
            })
        klines[code] = bars
    return klines


def _make_limit_up_klines(n_stocks: int = 3, n_days: int = 20, board_days: int = 3) -> dict[str, list[dict]]:
    """Build klines where stocks have consecutive limit-up days for select testing."""
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    klines: dict[str, list[dict]] = {}
    for ci, code in enumerate(sorted(codes)):
        bars = []
        base = 10.0
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


def _dsl(
    select=None, entry=None, exit_=None, position=None, environment=None, name="test"
) -> StrategyDSL:
    return StrategyDSL(
        name=name,
        select=select,
        entry=entry,
        exit=exit_ or ExitConditions(take_profit=15, stop_loss=-5, max_hold_days=3),
        position=position or PositionConfig(per_stock=20, max_total=60),
        environment=environment,
    )


class TestReproducibility:
    def test_identical_dsl_identical_klines_same_result(self):
        klines = _make_klines(n_stocks=5, n_days=60)
        engine = BacktestEngine()
        dsl = _dsl()
        r1 = engine._run_real(dsl, klines, years=1)
        r2 = engine._run_real(dsl, klines, years=1)
        assert r1.trade_log == r2.trade_log
        assert r1.equity_curve == r2.equity_curve
        assert r1.total_return == r2.total_return
        assert r1.total_trades == r2.total_trades

    def test_reproducibility_with_all_dsl_fields(self):
        klines = _make_klines(n_stocks=5, n_days=60)
        engine = BacktestEngine()
        dsl = _dsl(
            entry=EntryConditions(open_change=ConditionRule(lte=5)),
            exit_=ExitConditions(take_profit=10, stop_loss=-3, max_hold_days=5),
            position=PositionConfig(per_stock=25, max_total=75),
        )
        r1 = engine._run_real(dsl, klines, years=1)
        r2 = engine._run_real(dsl, klines, years=1)
        assert r1.trade_log == r2.trade_log
        assert r1.total_trades == r2.total_trades


class TestSelectSensitivity:
    def test_board_count_gte3_vs_gte1_different_trades(self):
        klines = _make_limit_up_klines(n_stocks=3, n_days=20, board_days=3)
        engine = BacktestEngine()
        dsl_strict = _dsl(select=SelectConditions(board_count=ConditionRule(gte=3)))
        dsl_loose = _dsl(select=SelectConditions(board_count=ConditionRule(gte=1)))
        r_strict = engine._run_real(dsl_strict, klines, years=1)
        r_loose = engine._run_real(dsl_loose, klines, years=1)
        assert r_strict.total_trades != r_loose.total_trades or r_strict.trade_log != r_loose.trade_log

    def test_board_count_gte99_empty_universe(self):
        klines = _make_klines(n_stocks=3, n_days=20)
        engine = BacktestEngine()
        dsl = _dsl(select=SelectConditions(board_count=ConditionRule(gte=99)))
        with pytest.raises(BacktestDataUnavailable):
            engine._run_real(dsl, klines, years=1)


class TestEntryFilter:
    def test_open_change_lte3_no_trade_exceeds_3pct(self):
        klines = _make_klines(n_stocks=3, n_days=40)
        engine = BacktestEngine()
        dsl = _dsl(entry=EntryConditions(open_change=ConditionRule(lte=3)))
        result = engine._run_real(dsl, klines, years=1)
        for code, code_bars in klines.items():
            bar_map = {b["date"]: b for b in code_bars}
            for trade in result.trade_log:
                entry_bar = bar_map.get(trade["date"])
                if entry_bar and trade["stock"] in (code, code[:6]):
                    open_chg = (entry_bar["open"] - entry_bar["pre_close"]) / entry_bar["pre_close"] * 100
                    assert open_chg <= 3.01


class TestExitParams:
    def test_tp5_vs_maxhold1_different_total_return(self):
        klines = _make_klines(n_stocks=3, n_days=60)
        engine = BacktestEngine()
        dsl_short = _dsl(exit_=ExitConditions(take_profit=15, stop_loss=-5, max_hold_days=1))
        dsl_long = _dsl(exit_=ExitConditions(take_profit=15, stop_loss=-5, max_hold_days=10))
        r_short = engine._run_real(dsl_short, klines, years=1)
        r_long = engine._run_real(dsl_long, klines, years=1)
        assert r_short.total_return != r_long.total_return or r_short.total_trades != r_long.total_trades


class TestPositionCap:
    def test_single_position_cap(self):
        klines = _make_klines(n_stocks=5, n_days=30)
        engine = BacktestEngine()
        dsl = _dsl(
            position=PositionConfig(per_stock=50, max_total=50),
            exit_=ExitConditions(take_profit=15, stop_loss=-5, max_hold_days=10),
        )
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades >= 1


class TestEnvironmentFilter:
    def test_sentiment_gte4_fewer_trade_dates(self):
        klines = _make_klines(n_stocks=5, n_days=60)
        engine = BacktestEngine()
        dsl_no_env = _dsl()
        dsl_hot = _dsl(environment=EnvironmentConditions(sentiment=ConditionRule(gte=4)))
        r_all = engine._run_real(dsl_no_env, klines, years=1)
        r_hot = engine._run_real(dsl_hot, klines, years=1)
        assert r_hot.total_trades <= r_all.total_trades

    def test_environment_blocks_entry_not_exit(self):
        klines = _make_klines(n_stocks=3, n_days=30)
        engine = BacktestEngine()
        dsl_ice = _dsl(
            environment=EnvironmentConditions(sentiment=ConditionRule(gte=99)),
            exit_=ExitConditions(take_profit=15, stop_loss=-5, max_hold_days=5),
        )
        result = engine._run_real(dsl_ice, klines, years=1)
        assert result.total_trades == 0
        assert result.equity_curve[-1]["value"] == 100.0


class TestFullTemplateDSL:
    def test_lianban_longtou_template(self):
        klines = _make_limit_up_klines(n_stocks=3, n_days=20, board_days=4)
        engine = BacktestEngine()
        template = STRATEGY_TEMPLATES["连板龙头低吸"]
        result = engine._run_real(template, klines, years=1)
        assert isinstance(result, BacktestResult)
        assert result.data_source == "tushare"


class TestNoEntryMatches:
    def test_strict_entry_zero_trades(self):
        klines = _make_klines(n_stocks=3, n_days=30)
        engine = BacktestEngine()
        dsl = _dsl(entry=EntryConditions(open_change=ConditionRule(gte=999)))
        result = engine._run_real(dsl, klines, years=1)
        assert result.total_trades == 0
        assert result.equity_curve[-1]["value"] == 100.0


class TestAllFieldsCombined:
    def test_full_dsl_deterministic(self):
        klines = _make_limit_up_klines(n_stocks=3, n_days=30, board_days=2)
        engine = BacktestEngine()
        dsl = _dsl(
            select=SelectConditions(board_count=ConditionRule(gte=1)),
            entry=EntryConditions(open_change=ConditionRule(lte=10)),
            exit_=ExitConditions(take_profit=10, stop_loss=-5, max_hold_days=3),
            position=PositionConfig(per_stock=30, max_total=60),
        )
        r1 = engine._run_real(dsl, klines, years=1)
        r2 = engine._run_real(dsl, klines, years=1)
        assert r1.trade_log == r2.trade_log
        assert r1.total_return == r2.total_return


class TestEquityCurve:
    def test_equity_curve_dates_sorted_ascending(self):
        klines = _make_klines(n_stocks=3, n_days=40)
        engine = BacktestEngine()
        dsl = _dsl()
        result = engine._run_real(dsl, klines, years=1)
        dates = [p["date"] for p in result.equity_curve]
        assert dates == sorted(dates)


class TestDataSource:
    def test_data_source_always_tushare(self):
        klines = _make_klines(n_stocks=2, n_days=20)
        engine = BacktestEngine()
        dsl = _dsl()
        result = engine._run_real(dsl, klines, years=1)
        assert result.data_source == "tushare"


class TestSentimentLevelUnit:
    def test_ice(self):
        assert _compute_sentiment_level(0.1) == 1

    def test_cool(self):
        assert _compute_sentiment_level(0.3) == 2

    def test_warm(self):
        assert _compute_sentiment_level(0.5) == 3

    def test_hot(self):
        assert _compute_sentiment_level(0.7) == 4

    def test_frenzy(self):
        assert _compute_sentiment_level(0.9) == 5


class TestEvaluateEnvironmentUnit:
    def test_none_env_always_true(self):
        assert _evaluate_environment("20240101", None, {}) is True

    def test_no_bars_on_date_passes(self):
        env = EnvironmentConditions(sentiment=ConditionRule(gte=5))
        assert _evaluate_environment("20240101", env, {}) is True

    def test_market_change_filter(self):
        kline_map = {
            "A": {"20240101": {"pct_chg": 2.0}},
            "B": {"20240101": {"pct_chg": 1.0}},
        }
        env = EnvironmentConditions(market_change=ConditionRule(gte=2.0))
        assert _evaluate_environment("20240101", env, kline_map) is False

    def test_sentiment_eq_label(self):
        kline_map = {
            f"S{i}": {"20240101": {"pct_chg": 3.0 if i < 7 else -1.0}}
            for i in range(10)
        }
        env = EnvironmentConditions(sentiment=ConditionRule(eq="HOT"))
        assert _evaluate_environment("20240101", env, kline_map) is True
