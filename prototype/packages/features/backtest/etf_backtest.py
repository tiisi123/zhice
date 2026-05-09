from __future__ import annotations

import logging
import math
from typing import Any

from packages.backtest.engine import BacktestDataUnavailable
from packages.features.etf.rotation import (
    ETF_SERIES,
    RECOMMENDED_POOL,
    TRADE_DATES,
    _build_etf_metrics,
    _calc_volatility,
    _clamp,
    _clone_series,
    _normalize,
    _pct_change,
)

logger = logging.getLogger(__name__)


def _generate_extended_sample_series(months: int) -> list[dict[str, Any]]:
    extended: list[dict[str, Any]] = []
    for item in ETF_SERIES:
        base_prices = list(item["prices"])
        base_flows = list(item["flows"])
        base_turnover = list(item["turnover"])

        prices: list[float] = list(base_prices)
        flows: list[float] = list(base_flows)
        turnover: list[float] = list(base_turnover)

        days_needed = months * 22
        while len(prices) < days_needed:
            cycle_len = len(base_prices)
            for i in range(cycle_len):
                if len(prices) >= days_needed:
                    break
                cycle_idx = len(prices) % cycle_len
                prev = prices[-1]
                base_return = _pct_change(base_prices[min(cycle_idx, cycle_len - 1)],
                                          base_prices[max(0, cycle_idx - 1)]) / 100
                drift = 0.0002 * (1 if base_return >= 0 else -1)
                new_price = round(prev * (1 + base_return + drift), 4)
                if new_price <= 0:
                    new_price = prev
                prices.append(new_price)

                flow_idx = cycle_idx % len(base_flows)
                flows.append(base_flows[flow_idx])
                turn_idx = cycle_idx % len(base_turnover)
                turnover.append(base_turnover[turn_idx])

        extended.append({
            "code": item["code"],
            "name": item["name"],
            "theme": item["theme"],
            "prices": prices[:days_needed],
            "flows": flows[:days_needed],
            "turnover": turnover[:days_needed],
            "is_live": False,
        })
    return extended


def _compute_signal_at_window(
    series_window: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = _build_etf_metrics(series_window)
    signals: list[dict[str, Any]] = []
    for m in metrics:
        start_score = m["start_score"]
        thresholds = m["risk_thresholds"]
        flow_3d = m["flow_3d"]
        change_5d = m["change_5d"]
        breakout = m["breakout"]
        stage = m["stage"]

        momentum_factor = _normalize(change_5d, -4.0, 8.0)
        trend_factor = _normalize(start_score, 0, 100)
        volatility = m["volatility"]
        vol_factor = 1.0 - _normalize(volatility, 0.5, 5.0)
        composite = momentum_factor * 0.40 + trend_factor * 0.35 + vol_factor * 0.25
        confidence = round(_clamp(composite * 100, 5, 95))

        if start_score >= thresholds["entry"] and flow_3d > 0 and (breakout or stage in ("启动", "加速")):
            signal = "加仓"
        elif start_score < thresholds["exit"] or (change_5d < -2.0 and flow_3d < -1.0):
            signal = "减仓"
        else:
            signal = "持有"

        signals.append({
            "code": m["code"],
            "name": m["name"],
            "signal": signal,
            "confidence": confidence,
        })
    return signals


def _simulate_etf_rotation(
    extended_series: list[dict[str, Any]],
    rebalance_interval: int = 22,
) -> tuple[list[dict], list[dict], list[dict]]:
    if not extended_series:
        return [], [], []

    total_days = min(len(s["prices"]) for s in extended_series)
    if total_days < 6:
        return [], [], []

    code_to_idx = {s["code"]: i for i, s in enumerate(extended_series)}
    equity = 100.0
    peak = equity
    max_dd = 0.0
    curve: list[dict] = []
    rebalance_log: list[dict] = []
    trades: list[dict] = []
    daily_returns: list[float] = []

    allocations: dict[str, float] = {}
    entry_prices: dict[str, float] = {}
    prev_equity = equity
    top_n = 5

    rebalance_points = list(range(5, total_days, rebalance_interval))
    if not rebalance_points:
        rebalance_points = [5]

    for day in range(total_days):
        if day in rebalance_points and day >= 5:
            window_series: list[dict[str, Any]] = []
            for s in extended_series:
                start_idx = max(0, day - 5)
                window_series.append({
                    "code": s["code"],
                    "name": s["name"],
                    "theme": s["theme"],
                    "prices": s["prices"][start_idx:day + 1],
                    "flows": s["flows"][start_idx:day + 1],
                    "turnover": s["turnover"][start_idx:day + 1],
                    "is_live": s.get("is_live", False),
                })

            signals = _compute_signal_at_window(window_series)
            buy_signals = [s for s in signals if s["signal"] == "加仓"]
            buy_signals.sort(key=lambda x: x["confidence"], reverse=True)
            selected = buy_signals[:top_n]

            if not selected:
                hold_signals = [s for s in signals if s["signal"] == "持有"]
                hold_signals.sort(key=lambda x: x["confidence"], reverse=True)
                selected = hold_signals[:top_n]

            for code in list(allocations.keys()):
                if code not in {s["code"] for s in selected}:
                    idx = code_to_idx.get(code)
                    if idx is not None:
                        exit_price = extended_series[idx]["prices"][day]
                        ep = entry_prices.get(code, exit_price)
                        pnl_pct = (exit_price - ep) / ep if ep > 0 else 0
                        weight = allocations[code]
                        equity += equity * weight * pnl_pct
                        trades.append({
                            "code": code,
                            "name": extended_series[idx]["name"],
                            "direction": "卖出",
                            "day": day,
                            "pnl": round(pnl_pct * 100, 2),
                        })

            new_alloc: dict[str, float] = {}
            new_entry: dict[str, float] = {}
            if selected:
                weight = round(1.0 / len(selected), 4)
                alloc_items: list[dict] = []
                for s in selected:
                    code = s["code"]
                    new_alloc[code] = weight
                    idx = code_to_idx[code]
                    new_entry[code] = extended_series[idx]["prices"][day]
                    alloc_items.append({"code": code, "name": s["name"], "weight": round(weight * 100, 1)})

                rebalance_log.append({"day": day, "allocations": alloc_items})

            allocations = new_alloc
            entry_prices = new_entry

        day_pnl = 0.0
        for code, weight in allocations.items():
            idx = code_to_idx.get(code)
            if idx is None or day < 1:
                continue
            prices = extended_series[idx]["prices"]
            if day < len(prices) and day - 1 >= 0:
                ret = (prices[day] - prices[day - 1]) / prices[day - 1] if prices[day - 1] > 0 else 0
                day_pnl += weight * ret

        equity *= (1 + day_pnl)
        daily_returns.append(day_pnl)
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        curve.append({"day": day, "value": round(equity, 4)})
        prev_equity = equity

    return trades, curve, rebalance_log


def _load_live_etf_data(years: int) -> list[dict[str, Any]] | None:
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        if not ts.configured:
            return None
    except Exception:
        return None

    pool_codes = {item["code"] for item in RECOMMENDED_POOL}
    series: list[dict[str, Any]] = []
    days_needed = years * 250

    try:
        for base_item in ETF_SERIES:
            code = base_item["code"]
            if code not in pool_codes:
                continue
            suffix = "SH" if code.startswith(("5", "6", "9")) else "SZ"
            ts_code = f"{code}.{suffix}"
            klines = ts.get_fund_daily(ts_code=ts_code, limit=days_needed + 20)
            if len(klines) >= 6:
                prices = [float(x.get("close", 0) or 0) for x in klines]
                if min(prices) <= 0:
                    return None
                amounts = [float(x.get("amount", 0) or 0) for x in klines]
                base_amount = sum(amounts) / len(amounts) if amounts else 1.0
                flows = []
                for i, k in enumerate(klines):
                    close_now = float(k.get("close", 0) or 0)
                    close_prev = float(klines[i - 1].get("close", close_now) or close_now) if i > 0 else close_now
                    ret = _pct_change(close_now, close_prev)
                    amt = float(k.get("amount", 0) or 0)
                    prev_w = [float(x.get("amount", 0) or 0) for x in klines[max(0, i - 3):i]]
                    avg_prev = sum(prev_w) / len(prev_w) if prev_w else amt
                    ratio = amt / avg_prev if avg_prev > 0 else 1.0
                    flow = (ratio - 1) * 3.2 + ret * 0.38
                    flows.append(round(_clamp(flow, -5.5, 9.5), 2))

                turnover = []
                for k in klines:
                    tr = float(k.get("turnover", 0) or 0)
                    if tr > 0:
                        turnover.append(round(_clamp(tr, 0.4, 12.0), 2))
                    else:
                        amt = float(k.get("amount", 0) or 0)
                        turnover.append(round(_clamp((amt / base_amount) * 1.8, 0.6, 5.2), 2))

                series.append({
                    "code": code,
                    "name": base_item["name"],
                    "theme": base_item["theme"],
                    "prices": prices,
                    "flows": flows,
                    "turnover": turnover,
                    "is_live": True,
                })
            else:
                return None
    except Exception:
        return None

    if len(series) < len(ETF_SERIES):
        return None
    return series


def run_etf_backtest(
    mode: str = "auto",
    years: int = 1,
) -> dict:
    strategy_name = "ETF轮动策略"
    normalized_mode = (mode or "auto").strip().lower()

    if normalized_mode == "sample":
        months = max(years * 12, 3)
        extended = _generate_extended_sample_series(months)
        data_mode = "sample"
        data_source = "sample_engine"
    else:
        live_series = _load_live_etf_data(years)
        if live_series:
            extended = live_series
            data_mode = "live"
            data_source = "tushare_fund_daily"
        else:
            raise BacktestDataUnavailable("TuShare ETF 实盘数据不可用，ETF 回测未使用演示数据自动兜底；可显式选择 mode=sample 查看演示。")

    trades, curve, rebalance_log = _simulate_etf_rotation(extended, rebalance_interval=22)

    total_trades = len(trades)
    if len(curve) >= 2:
        total_return = curve[-1]["value"] - curve[0]["value"]
    else:
        total_return = 0.0

    values = [pt["value"] for pt in curve]
    peak_val = values[0] if values else 100.0
    max_dd = 0.0
    for v in values:
        peak_val = max(peak_val, v)
        dd = (peak_val - v) / peak_val if peak_val > 0 else 0
        max_dd = max(max_dd, dd)

    actual_days = len(curve)
    actual_years = max(actual_days / 250, 0.1)
    annualized = total_return / actual_years if actual_years > 0 else 0

    daily_returns: list[float] = []
    for i in range(1, len(values)):
        daily_returns.append((values[i] - values[i - 1]) / values[i - 1] if values[i - 1] > 0 else 0)

    if daily_returns:
        mean_r = sum(daily_returns) / len(daily_returns)
        var_r = sum((r - mean_r) ** 2 for r in daily_returns) / max(len(daily_returns) - 1, 1)
        std_r = math.sqrt(var_r)
        sharpe = (mean_r / std_r * math.sqrt(250)) if std_r > 0 else 0
    else:
        sharpe = 0

    return {
        "strategy_name": strategy_name,
        "data_mode": data_mode,
        "data_source": data_source,
        "total_return": round(total_return, 2),
        "annualized_return": round(annualized, 2),
        "max_drawdown": round(-max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_trades": total_trades,
        "equity_curve": curve,
        "rebalance_log": rebalance_log,
        "etf_count": len(RECOMMENDED_POOL),
    }
