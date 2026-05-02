"""Tests for _compute_stock_features, _match_condition, and _evaluate_select."""

from __future__ import annotations

import pytest

from packages.backtest.dsl_schema import ConditionRule, SelectConditions
from packages.backtest.engine import (
    BacktestDataUnavailable,
    _compute_stock_features,
    _evaluate_select,
    _match_condition,
)


def _make_bars(closes: list[float], pre_closes: list[float] | None = None) -> list[dict]:
    """Build synthetic kline bars for testing."""
    bars = []
    for i, close in enumerate(closes):
        pc = pre_closes[i] if pre_closes else (closes[i - 1] if i > 0 else close / 1.05)
        bars.append({
            "date": f"2024010{i + 1}" if i < 9 else f"202401{i + 1}",
            "open": close * 0.99,
            "close": close,
            "pre_close": pc,
            "vol": 1000000,
            "amount": 50000000,
            "volume": 1000000,
        })
    return bars


def _make_klines(codes: list[str], bars_per_code: list[list[dict]] | None = None) -> dict[str, list[dict]]:
    if bars_per_code:
        return {code: bars for code, bars in zip(codes, bars_per_code)}
    return {code: _make_bars([10.0, 11.0, 12.0]) for code in codes}


def _make_features(codes: list[str], overrides: dict[str, dict] | None = None) -> dict[str, dict]:
    feat = {}
    for code in codes:
        base = {"code": code, "board_count": 0, "turnover_rate": 0.02, "market_cap": 1e9}
        if overrides and code in overrides:
            base.update(overrides[code])
        feat[code] = base
    return feat


# --- _match_condition tests ---

class TestMatchCondition:
    def test_gte_pass(self):
        assert _match_condition(5, ConditionRule(gte=3)) is True

    def test_gte_fail(self):
        assert _match_condition(2, ConditionRule(gte=3)) is False

    def test_lte_pass(self):
        assert _match_condition(2, ConditionRule(lte=5)) is True

    def test_lte_fail(self):
        assert _match_condition(10, ConditionRule(lte=5)) is False

    def test_eq_pass(self):
        assert _match_condition("ABC", ConditionRule(eq="ABC")) is True

    def test_eq_fail(self):
        assert _match_condition("ABC", ConditionRule(eq="DEF")) is False

    def test_combined_gte_lte_pass(self):
        assert _match_condition(5, ConditionRule(gte=3, lte=10)) is True

    def test_combined_gte_lte_fail(self):
        assert _match_condition(15, ConditionRule(gte=3, lte=10)) is False

    def test_non_numeric_gte_fail(self):
        assert _match_condition("abc", ConditionRule(gte=3)) is False


# --- _compute_stock_features tests ---

class TestComputeStockFeatures:
    def test_empty_bars(self):
        feat = _compute_stock_features("000001.SZ", [])
        assert feat["board_count"] == 0
        assert feat["turnover_rate"] == 0.0

    def test_consecutive_limit_up(self):
        closes = [10.0, 11.0, 12.1, 13.3, 14.6]
        pre_closes = [9.5, 10.0, 11.0, 12.1, 13.3]
        bars = _make_bars(closes, pre_closes)
        feat = _compute_stock_features("600519.SH", bars)
        assert feat["board_count"] >= 3

    def test_no_limit_up(self):
        closes = [10.0, 10.1, 10.0, 9.9, 10.0]
        bars = _make_bars(closes)
        feat = _compute_stock_features("600519.SH", bars)
        assert feat["board_count"] == 0


# --- _evaluate_select tests ---

class TestEvaluateSelect:
    def test_no_select_returns_all(self):
        codes = ["000001.SZ", "600519.SH", "300750.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes)
        result = _evaluate_select(None, klines, features)
        assert result == sorted(codes)

    def test_board_count_gte_filters(self):
        codes = ["A.SZ", "B.SZ", "C.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {"A.SZ": {"board_count": 5}, "B.SZ": {"board_count": 1}, "C.SZ": {"board_count": 3}})
        sel = SelectConditions(board_count=ConditionRule(gte=3))
        result = _evaluate_select(sel, klines, features)
        assert "A.SZ" in result
        assert "C.SZ" in result
        assert "B.SZ" not in result

    def test_is_leader_true_passes_all_when_no_data(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes)
        sel = SelectConditions(is_leader=True)
        result = _evaluate_select(sel, klines, features)
        assert result == sorted(codes)

    def test_rank_top3_returns_exactly_3(self):
        codes = ["A.SZ", "B.SZ", "C.SZ", "D.SZ", "E.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {
            "A.SZ": {"board_count": 5},
            "B.SZ": {"board_count": 4},
            "C.SZ": {"board_count": 3},
            "D.SZ": {"board_count": 2},
            "E.SZ": {"board_count": 1},
        })
        sel = SelectConditions(board_count=ConditionRule(rank="top3"))
        result = _evaluate_select(sel, klines, features)
        assert len(result) == 3
        assert set(result) == {"A.SZ", "B.SZ", "C.SZ"}

    def test_multiple_conditions_and_compose(self):
        codes = ["A.SZ", "B.SZ", "C.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {
            "A.SZ": {"board_count": 5, "turnover_rate": 0.01},
            "B.SZ": {"board_count": 3, "turnover_rate": 0.05},
            "C.SZ": {"board_count": 1, "turnover_rate": 0.08},
        })
        sel = SelectConditions(
            board_count=ConditionRule(gte=3),
            turnover_rate=ConditionRule(lte=0.03),
        )
        result = _evaluate_select(sel, klines, features)
        assert result == ["A.SZ"]

    def test_empty_klines_raises(self):
        with pytest.raises(BacktestDataUnavailable):
            _evaluate_select(
                SelectConditions(board_count=ConditionRule(gte=1)),
                {},
                {},
            )

    def test_all_filtered_out_raises(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {"A.SZ": {"board_count": 0}, "B.SZ": {"board_count": 0}})
        sel = SelectConditions(board_count=ConditionRule(gte=10))
        with pytest.raises(BacktestDataUnavailable, match="选股条件过滤后无标的通过"):
            _evaluate_select(sel, klines, features)

    def test_deterministic_same_input_same_output(self):
        codes = ["C.SZ", "A.SZ", "B.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {"A.SZ": {"board_count": 3}, "B.SZ": {"board_count": 1}, "C.SZ": {"board_count": 5}})
        sel = SelectConditions(board_count=ConditionRule(gte=2))
        r1 = _evaluate_select(sel, klines, features)
        r2 = _evaluate_select(sel, klines, features)
        assert r1 == r2

    def test_market_cap_gte_filter(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes, {"A.SZ": {"market_cap": 100}, "B.SZ": {"market_cap": 30}})
        sel = SelectConditions(market_cap=ConditionRule(gte=50))
        result = _evaluate_select(sel, klines, features)
        assert result == ["A.SZ"]

    def test_seal_amount_passes_when_no_data(self):
        codes = ["A.SZ", "B.SZ"]
        klines = _make_klines(codes)
        features = _make_features(codes)
        sel = SelectConditions(seal_amount=ConditionRule(gte=5000))
        result = _evaluate_select(sel, klines, features)
        assert result == sorted(codes)
