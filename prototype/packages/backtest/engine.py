from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .dsl_schema import StrategyDSL

BACKTEST_STOCKS = [
    "600519.SH", "000858.SZ", "601012.SH", "300750.SZ", "002475.SZ",
    "600036.SH", "000651.SZ", "002594.SZ", "300059.SZ", "601318.SH",
    "000001.SZ", "600900.SH", "601888.SH", "300124.SZ", "002714.SZ",
]

STOCK_NAMES = {
    "600519.SH": "贵州茅台", "000858.SZ": "五粮液", "601012.SH": "隆基绿能",
    "300750.SZ": "宁德时代", "002475.SZ": "立讯精密", "600036.SH": "招商银行",
    "000651.SZ": "格力电器", "002594.SZ": "比亚迪", "300059.SZ": "东方财富",
    "601318.SH": "中国平安", "000001.SZ": "平安银行", "600900.SH": "长江电力",
    "601888.SH": "中国中免", "300124.SZ": "汇川技术", "002714.SZ": "牧原股份",
}


class BacktestDataUnavailable(RuntimeError):
    pass


@dataclass
class BacktestResult:
    strategy_name: str = ""
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    calmar_ratio: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    avg_hold_days: float = 0.0
    equity_curve: list[dict] = field(default_factory=list)
    trade_log: list[dict] = field(default_factory=list)
    data_source: str = "tushare"

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "total_return": round(self.total_return, 2),
            "annualized_return": round(self.annualized_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "win_rate": round(self.win_rate, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "profit_loss_ratio": round(self.profit_loss_ratio, 2),
            "total_trades": self.total_trades,
            "win_trades": self.win_trades,
            "loss_trades": self.loss_trades,
            "avg_hold_days": round(self.avg_hold_days, 1),
            "equity_curve": self.equity_curve,
            "trade_log": self.trade_log,
            "data_source": self.data_source,
        }


def _load_klines(years: int) -> dict[str, list[dict]]:
    """Load real klines from TuShare, fall back to empty on failure."""
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        if not ts.configured:
            return {}
    except Exception:
        return {}

    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y%m%d")
    klines: dict[str, list[dict]] = {}
    codes = random.sample(BACKTEST_STOCKS, min(8, len(BACKTEST_STOCKS)))
    for code in codes:
        rows = ts.get_daily(code, start_date=start, end_date=end)
        if rows:
            klines[code] = rows
    return klines


class BacktestEngine:
    def run(self, dsl: StrategyDSL, years: int = 3) -> BacktestResult:
        klines = _load_klines(years)
        if klines:
            return self._run_real(dsl, klines, years)
        raise BacktestDataUnavailable("真实历史行情不可用，请配置 TUSHARE_TOKEN 或稍后重试")

    def _run_real(self, dsl: StrategyDSL, klines: dict[str, list[dict]], years: int) -> BacktestResult:
        tp = dsl.exit.take_profit / 100
        sl = abs(dsl.exit.stop_loss) / 100
        max_hold = dsl.exit.max_hold_days

        equity = 100.0
        peak = equity
        max_dd = 0.0
        trades = []
        curve = []
        daily_returns = []
        total_hold = 0

        all_dates = sorted({bar["date"] for bars in klines.values() for bar in bars})
        if not all_dates:
            raise BacktestDataUnavailable("真实历史行情为空，无法生成回测结果")

        kline_map: dict[str, dict[str, dict]] = {}
        for code, bars in klines.items():
            kline_map[code] = {bar["date"]: bar for bar in bars}

        codes = list(klines.keys())
        position: dict | None = None
        prev_equity = equity
        trade_interval = max(5, 20 // max(len(codes), 1))

        for i, date in enumerate(all_dates):
            if position is not None:
                code = position["code"]
                bar = kline_map.get(code, {}).get(date)
                if bar:
                    current_price = bar["close"]
                    entry_price = position["entry_price"]
                    pnl_pct = (current_price - entry_price) / entry_price
                    hold_days = position["hold_days"] + 1
                    position["hold_days"] = hold_days

                    should_exit = pnl_pct >= tp or pnl_pct <= -sl or hold_days >= max_hold
                    if should_exit:
                        pnl_value = equity * (dsl.position.per_stock / 100) * pnl_pct
                        equity += pnl_value
                        trades.append({
                            "date": position["entry_date"],
                            "stock": STOCK_NAMES.get(code, code),
                            "direction": "买入",
                            "hold_days": hold_days,
                            "pnl": round(pnl_pct * 100, 2),
                            "result": "盈利" if pnl_pct > 0 else "亏损",
                        })
                        total_hold += hold_days
                        position = None

            elif i % trade_interval == 0:
                code = random.choice(codes)
                bar = kline_map.get(code, {}).get(date)
                if bar and bar["open"] > 0:
                    position = {
                        "code": code,
                        "entry_price": bar["open"],
                        "entry_date": date,
                        "hold_days": 0,
                    }

            if equity != prev_equity or i % 10 == 0:
                curve.append({"date": date, "value": round(equity, 2)})
            daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_ret)
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
            prev_equity = equity

        if position is not None:
            code = position["code"]
            last_bars = klines.get(code, [])
            if last_bars:
                pnl_pct = (last_bars[-1]["close"] - position["entry_price"]) / position["entry_price"]
                pnl_value = equity * (dsl.position.per_stock / 100) * pnl_pct
                equity += pnl_value
                trades.append({
                    "date": position["entry_date"],
                    "stock": STOCK_NAMES.get(code, code),
                    "direction": "买入",
                    "hold_days": position["hold_days"],
                    "pnl": round(pnl_pct * 100, 2),
                    "result": "盈利" if pnl_pct > 0 else "亏损",
                })
                total_hold += position["hold_days"]

        if not curve or curve[-1]["date"] != all_dates[-1]:
            curve.append({"date": all_dates[-1], "value": round(equity, 2)})

        total_trades = len(trades)
        win_trades = sum(1 for t in trades if t["result"] == "盈利")
        loss_trades = total_trades - win_trades
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0

        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [abs(t["pnl"]) for t in trades if t["pnl"] < 0]
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 1
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0

        total_return = equity - 100.0
        actual_years = max(len(all_dates) / 250, 0.5)
        annualized = total_return / actual_years

        import math
        if daily_returns:
            mean_r = sum(daily_returns) / len(daily_returns)
            var_r = sum((r - mean_r) ** 2 for r in daily_returns) / max(len(daily_returns) - 1, 1)
            std_r = math.sqrt(var_r)
            sharpe = (mean_r / std_r * math.sqrt(250)) if std_r > 0 else 0
        else:
            sharpe = 0

        calmar = annualized / (max_dd * 100) if max_dd > 0 else 0

        return BacktestResult(
            strategy_name=dsl.name,
            total_return=total_return,
            annualized_return=annualized,
            max_drawdown=round(-max_dd * 100, 2),
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            calmar_ratio=calmar,
            profit_loss_ratio=pl_ratio,
            total_trades=total_trades,
            win_trades=win_trades,
            loss_trades=loss_trades,
            avg_hold_days=total_hold / total_trades if total_trades > 0 else 0,
            equity_curve=curve,
            trade_log=trades,
            data_source="tushare",
        )
