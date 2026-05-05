from __future__ import annotations

import logging
import math
from dataclasses import asdict
from datetime import datetime, timedelta

from packages.backtest.engine import BACKTEST_STOCKS, STOCK_NAMES, BacktestResult

logger = logging.getLogger(__name__)

SUB_STRATEGY_CONFIG = {
    "首板": {"board_filter": lambda bc: bc == 1, "take_profit": 0.08, "stop_loss": 0.03, "max_hold": 1},
    "二板": {"board_filter": lambda bc: bc == 2, "take_profit": 0.08, "stop_loss": 0.03, "max_hold": 2},
    "龙头": {"board_filter": lambda bc: bc >= 3, "take_profit": 0.08, "stop_loss": 0.03, "max_hold": 3},
}


def _generate_sample_trading_days(count: int = 20) -> list[str]:
    base = datetime(2026, 1, 5)
    days: list[str] = []
    current = base
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days


def _generate_sample_limit_up_data(
    stocks: list[str], trading_days: list[str]
) -> dict[str, list[dict]]:
    data: dict[str, list[dict]] = {}
    for si, code in enumerate(sorted(stocks)):
        bars: list[dict] = []
        base_price = 10.0 + si * 2.5
        price = base_price
        for di, date in enumerate(trading_days):
            seed = (si * 1000 + di * 7 + 42) % 100
            is_limit_up = seed < (45 - si * 2)
            if is_limit_up:
                pct_chg = 9.98
                close = round(price * 1.0998, 2)
            else:
                delta = ((seed % 7) - 3) * 0.5
                pct_chg = round(delta, 2)
                close = round(price * (1 + delta / 100), 2)

            open_price = round(price * (1 + ((seed % 5) - 2) * 0.3 / 100), 2)
            bars.append({
                "date": date,
                "code": code,
                "open": open_price,
                "close": close,
                "pre_close": round(price, 2),
                "pct_chg": pct_chg,
                "vol": 100000 + seed * 1000,
                "amount": 500000 + seed * 5000,
            })
            price = close
        data[code] = bars
    return data


def _compute_board_count(bars: list[dict], day_idx: int) -> int:
    count = 0
    for i in range(day_idx, -1, -1):
        if bars[i]["pct_chg"] >= 9.9:
            count += 1
        else:
            break
    return count


def _simulate_board_trades(
    stock_data: dict[str, list[dict]],
    trading_days: list[str],
    board_filter,
    take_profit: float,
    stop_loss: float,
    max_hold: int,
) -> tuple[list[dict], list[dict]]:
    equity = 100.0
    peak = equity
    max_dd = 0.0
    trades: list[dict] = []
    curve: list[dict] = []
    daily_returns: list[float] = []
    positions: list[dict] = []
    prev_equity = equity
    per_stock_pct = 0.10

    day_map: dict[str, dict[str, dict]] = {}
    for code, bars in stock_data.items():
        for bar in bars:
            day_map.setdefault(bar["date"], {})[code] = bar

    for di, date in enumerate(trading_days):
        exited: list[int] = []
        for pi, pos in enumerate(positions):
            code = pos["code"]
            bar = day_map.get(date, {}).get(code)
            if not bar:
                continue
            entry_price = pos["entry_price"]
            pnl_pct = (bar["close"] - entry_price) / entry_price
            pos["hold_days"] += 1
            should_exit = pnl_pct >= take_profit or pnl_pct <= -stop_loss or pos["hold_days"] >= max_hold
            if should_exit:
                pnl_value = equity * per_stock_pct * pnl_pct
                equity += pnl_value
                trades.append({
                    "date": pos["entry_date"],
                    "exit_date": date,
                    "stock": STOCK_NAMES.get(code, code),
                    "code": code,
                    "direction": "买入",
                    "hold_days": pos["hold_days"],
                    "pnl": round(pnl_pct * 100, 2),
                    "result": "盈利" if pnl_pct > 0 else "亏损",
                })
                exited.append(pi)

        for pi in reversed(exited):
            positions.pop(pi)

        held_codes = {p["code"] for p in positions}
        for code in sorted(stock_data.keys()):
            if code in held_codes or len(positions) >= 3:
                break
            bars = stock_data[code]
            if di >= len(bars):
                continue
            bc = _compute_board_count(bars, di)
            if not board_filter(bc):
                continue
            if di + 1 < len(trading_days):
                next_date = trading_days[di + 1]
                next_bar = day_map.get(next_date, {}).get(code)
                if next_bar and next_bar["open"] > 0:
                    positions.append({
                        "code": code,
                        "entry_price": next_bar["open"],
                        "entry_date": next_date,
                        "hold_days": 0,
                    })

        daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
        daily_returns.append(daily_ret)
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)
        curve.append({"date": date, "value": round(equity, 2)})
        prev_equity = equity

    for pos in positions:
        code = pos["code"]
        bars = stock_data.get(code, [])
        if bars:
            last_close = bars[-1]["close"]
            pnl_pct = (last_close - pos["entry_price"]) / pos["entry_price"]
            pnl_value = equity * per_stock_pct * pnl_pct
            equity += pnl_value
            trades.append({
                "date": pos["entry_date"],
                "exit_date": trading_days[-1],
                "stock": STOCK_NAMES.get(code, code),
                "code": code,
                "direction": "买入",
                "hold_days": pos["hold_days"],
                "pnl": round(pnl_pct * 100, 2),
                "result": "盈利" if pnl_pct > 0 else "亏损",
            })

    if curve and curve[-1]["value"] != round(equity, 2):
        curve[-1]["value"] = round(equity, 2)

    return trades, curve


def _compute_metrics(
    trades: list[dict],
    curve: list[dict],
    strategy_name: str,
    data_mode: str,
    data_source: str,
    years: int,
) -> dict:
    total_trades = len(trades)
    win_trades = sum(1 for t in trades if t["result"] == "盈利")
    loss_trades = total_trades - win_trades
    win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0

    wins = [t["pnl"] for t in trades if t["pnl"] > 0]
    losses = [abs(t["pnl"]) for t in trades if t["pnl"] < 0]
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 1
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

    total_hold = sum(t["hold_days"] for t in trades)
    avg_hold_days = total_hold / total_trades if total_trades > 0 else 0

    consec = 0
    max_consec = 0
    for t in trades:
        if t["result"] == "亏损":
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0

    if len(curve) >= 2:
        total_return = curve[-1]["value"] - curve[0]["value"]
    else:
        total_return = 0.0

    values = [pt["value"] for pt in curve]
    peak = values[0] if values else 100.0
    max_dd = 0.0
    for v in values:
        peak = max(peak, v)
        dd = (peak - v) / peak if peak > 0 else 0
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
        "win_rate": round(win_rate, 2),
        "profit_loss_ratio": round(profit_loss_ratio, 2),
        "max_consecutive_loss": max_consec,
        "total_trades": total_trades,
        "win_trades": win_trades,
        "loss_trades": loss_trades,
        "avg_hold_days": round(avg_hold_days, 1),
        "equity_curve": curve,
        "trade_log": trades,
    }


def _load_live_limit_up_data(years: int) -> dict[str, list[dict]] | None:
    try:
        from packages.connectors.registry import get_kpl
        kpl = get_kpl()
        if not kpl.configured:
            return None
    except Exception:
        return None

    end = datetime.now()
    start = end - timedelta(days=years * 365)
    current = start
    all_data: dict[str, list[dict]] = {}
    day_count = 0
    while current <= end and day_count < 500:
        if current.weekday() < 5:
            date_str = current.strftime("%Y-%m-%d")
            try:
                rows = kpl.get_limit_up(date_str)
                if rows:
                    for row in rows:
                        code = row.get("code", "")
                        if code in BACKTEST_STOCKS:
                            all_data.setdefault(code, []).append({
                                "date": date_str,
                                "code": code,
                                "open": float(row.get("open", 0) or 0),
                                "close": float(row.get("close", 0) or 0),
                                "pre_close": float(row.get("pre_close", 0) or 0),
                                "pct_chg": float(row.get("pct_chg", 0) or 0),
                                "vol": float(row.get("vol", 0) or 0),
                                "amount": float(row.get("amount", 0) or 0),
                            })
                    day_count += 1
            except Exception:
                pass
        current += timedelta(days=1)

    if not all_data:
        return None
    return all_data


def run_board_backtest(
    sub_strategy: str = "首板",
    mode: str = "sample",
    years: int = 1,
) -> dict:
    config = SUB_STRATEGY_CONFIG.get(sub_strategy, SUB_STRATEGY_CONFIG["首板"])
    strategy_name = f"打板策略-{sub_strategy}"

    if mode == "sample":
        trading_days = _generate_sample_trading_days(20)
        stock_data = _generate_sample_limit_up_data(sorted(BACKTEST_STOCKS), trading_days)
        data_mode = "sample"
        data_source = "sample_engine"
    else:
        live_data = _load_live_limit_up_data(years)
        if live_data:
            all_dates = sorted({bar["date"] for bars in live_data.values() for bar in bars})
            stock_data = live_data
            trading_days = all_dates
            data_mode = "live"
            data_source = "kpl_limit_up"
        else:
            trading_days = _generate_sample_trading_days(20)
            stock_data = _generate_sample_limit_up_data(sorted(BACKTEST_STOCKS), trading_days)
            data_mode = "sample"
            data_source = "sample_engine"
            logger.info("live KPL data unavailable, falling back to sample mode")

    trades, curve = _simulate_board_trades(
        stock_data,
        trading_days,
        config["board_filter"],
        config["take_profit"],
        config["stop_loss"],
        config["max_hold"],
    )

    return _compute_metrics(trades, curve, strategy_name, data_mode, data_source, years)
