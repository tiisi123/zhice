from __future__ import annotations

import random
from itertools import product

from .dsl_schema import StrategyDSL, ExitConditions
from .engine import BacktestEngine, BacktestResult


class ParameterOptimizer:
    def __init__(self):
        self._engine = BacktestEngine()

    def grid_search(
        self,
        base_dsl: StrategyDSL,
        take_profit_range: list[float] | None = None,
        stop_loss_range: list[float] | None = None,
        hold_days_range: list[int] | None = None,
        years: int = 3,
    ) -> list[dict]:
        if take_profit_range is None:
            take_profit_range = [5, 8, 10, 15, 20]
        if stop_loss_range is None:
            stop_loss_range = [-3, -5, -7, -10]
        if hold_days_range is None:
            hold_days_range = [1, 2, 3, 5]
        results = []
        for tp, sl, hd in product(take_profit_range, stop_loss_range, hold_days_range):
            dsl = base_dsl.model_copy()
            dsl.exit = ExitConditions(**{"止盈": tp, "止损": sl, "持有天数上限": hd})
            bt = self._engine.run(dsl, years)
            results.append({
                "take_profit": tp,
                "stop_loss": sl,
                "hold_days": hd,
                **bt.to_dict(),
            })
        results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
        return results


class SimulatedTrader:
    def __init__(self, initial_capital: float = 1_000_000):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: list[dict] = []
        self.trade_log: list[dict] = []
        self.day = 0

    def buy(self, code: str, name: str, price: float, amount: float) -> dict:
        shares = int(amount / price / 100) * 100
        if shares <= 0 or price * shares > self.capital:
            raise ValueError("资金不足或数量不合法")
        cost = price * shares
        self.capital -= cost
        pos = {"code": code, "name": name, "price": price, "shares": shares, "day": self.day}
        self.positions.append(pos)
        trade = {"action": "buy", "code": code, "name": name, "price": price, "shares": shares, "day": self.day}
        self.trade_log.append(trade)
        return trade

    def sell(self, code: str, price: float) -> dict:
        pos = next((p for p in self.positions if p["code"] == code), None)
        if not pos:
            raise ValueError(f"无 {code} 的持仓")
        revenue = price * pos["shares"]
        pnl = revenue - pos["price"] * pos["shares"]
        self.capital += revenue
        self.positions.remove(pos)
        trade = {"action": "sell", "code": code, "price": price, "shares": pos["shares"],
                 "pnl": round(pnl, 2), "pnl_rate": round(pnl / (pos["price"] * pos["shares"]) * 100, 2), "day": self.day}
        self.trade_log.append(trade)
        return trade

    def next_day(self):
        self.day += 1
        for pos in self.positions:
            pos["price"] *= (1 + random.uniform(-0.03, 0.03))
            pos["price"] = round(pos["price"], 2)

    def status(self) -> dict:
        pos_value = sum(p["price"] * p["shares"] for p in self.positions)
        total = self.capital + pos_value
        return {
            "day": self.day,
            "capital": round(self.capital, 2),
            "position_value": round(pos_value, 2),
            "total_value": round(total, 2),
            "total_return": round((total - self.initial_capital) / self.initial_capital * 100, 2),
            "positions": [{"code": p["code"], "name": p["name"], "shares": p["shares"],
                          "current_price": p["price"], "value": round(p["price"] * p["shares"], 2)} for p in self.positions],
            "trade_count": len(self.trade_log),
        }
