from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .dsl_schema import ConditionRule, EntryConditions, EnvironmentConditions, SelectConditions, StrategyDSL

logger = logging.getLogger(__name__)

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
    """Load real klines from TuShare for ALL BACKTEST_STOCKS deterministically."""
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
    for code in sorted(BACKTEST_STOCKS):
        rows = ts.get_daily(code, start_date=start, end_date=end)
        if rows:
            klines[code] = rows
    return klines


def _compute_stock_features(code: str, bars: list[dict]) -> dict:
    """Derive deterministic features from kline bars for select evaluation."""
    if not bars:
        return {"code": code, "board_count": 0, "turnover_rate": 0.0, "market_cap": 0.0}

    sorted_bars = sorted(bars, key=lambda b: b["date"])
    trailing = sorted_bars[-10:] if len(sorted_bars) >= 10 else sorted_bars

    board_count = 0
    for bar in reversed(trailing):
        close = bar.get("close", 0)
        pre_close = bar.get("pre_close", 0)
        if pre_close > 0 and close >= pre_close * 1.095:
            board_count += 1
        else:
            break

    latest = sorted_bars[-1]
    volume = latest.get("vol", latest.get("volume", 0)) or 0
    amount = latest.get("amount", 0) or 0
    close = latest.get("close", 0) or 0
    turnover_rate = (volume / amount) if amount > 0 else 0.0
    market_cap = close * volume

    return {
        "code": code,
        "board_count": board_count,
        "turnover_rate": turnover_rate,
        "market_cap": market_cap,
    }


def _match_condition(value, rule: ConditionRule) -> bool:
    """Check if a single value satisfies a ConditionRule. Returns True if all set operators pass."""
    if rule.gte is not None:
        try:
            if float(value) < rule.gte:
                return False
        except (TypeError, ValueError):
            return False
    if rule.lte is not None:
        try:
            if float(value) > rule.lte:
                return False
        except (TypeError, ValueError):
            return False
    if rule.eq is not None:
        if str(value) != str(rule.eq):
            return False
    return True


def _evaluate_select(
    dsl_select: Optional[SelectConditions],
    klines: dict[str, list[dict]],
    features: dict[str, dict],
) -> list[str]:
    """Filter stock codes by DSL select conditions. Returns sorted list of passing codes."""
    codes = sorted(klines.keys())

    if dsl_select is None:
        return codes

    rank_field: Optional[str] = None
    rank_n: Optional[int] = None

    passing: list[str] = []
    for code in codes:
        feat = features.get(code, {})
        ok = True

        if dsl_select.board_count is not None:
            if dsl_select.board_count.rank:
                rank_field = "board_count"
                try:
                    rank_n = int(dsl_select.board_count.rank.replace("top", ""))
                except ValueError:
                    rank_n = 3
            elif not _match_condition(feat.get("board_count", 0), dsl_select.board_count):
                ok = False

        if dsl_select.turnover_rate is not None:
            if dsl_select.turnover_rate.rank:
                rank_field = "turnover_rate"
                try:
                    rank_n = int(dsl_select.turnover_rate.rank.replace("top", ""))
                except ValueError:
                    rank_n = 3
            elif not _match_condition(feat.get("turnover_rate", 0), dsl_select.turnover_rate):
                ok = False

        if dsl_select.market_cap is not None:
            if dsl_select.market_cap.rank:
                rank_field = "market_cap"
                try:
                    rank_n = int(dsl_select.market_cap.rank.replace("top", ""))
                except ValueError:
                    rank_n = 3
            elif not _match_condition(feat.get("market_cap", 0), dsl_select.market_cap):
                ok = False

        if dsl_select.theme_hot is not None:
            if dsl_select.theme_hot.rank:
                rank_field = "theme_hot"
                try:
                    rank_n = int(dsl_select.theme_hot.rank.replace("top", ""))
                except ValueError:
                    rank_n = 3
            elif feat.get("theme_hot") is not None:
                if not _match_condition(feat["theme_hot"], dsl_select.theme_hot):
                    ok = False

        if dsl_select.seal_amount is not None:
            if dsl_select.seal_amount.rank:
                rank_field = "seal_amount"
                try:
                    rank_n = int(dsl_select.seal_amount.rank.replace("top", ""))
                except ValueError:
                    rank_n = 3
            elif feat.get("seal_amount") is not None:
                if not _match_condition(feat["seal_amount"], dsl_select.seal_amount):
                    ok = False

        if dsl_select.is_leader is not None and dsl_select.is_leader is True:
            pass

        if dsl_select.limit_reason is not None:
            lr = feat.get("limit_reason")
            if lr is not None and lr != dsl_select.limit_reason:
                ok = False

        if dsl_select.sector is not None:
            sec = feat.get("sector")
            if sec is not None and sec != dsl_select.sector:
                ok = False

        if ok:
            passing.append(code)

    if rank_field is not None and rank_n is not None:
        passing.sort(key=lambda c: features.get(c, {}).get(rank_field, 0), reverse=True)
        passing = passing[:rank_n]

    result = sorted(passing)

    logger.info("select filter: %d/%d stocks passed", len(result), len(codes))

    if not result:
        raise BacktestDataUnavailable(
            f"选股条件过滤后无标的通过（{len(codes)} 只股票全部被过滤），请放宽选股条件"
        )

    return result


def _evaluate_entry(bar: dict, dsl_entry: Optional[EntryConditions]) -> bool:
    """Check if a bar satisfies DSL entry conditions. Returns True if all conditions pass."""
    if dsl_entry is None:
        return True

    if dsl_entry.open_change is not None:
        pre_close = bar.get("pre_close", 0)
        open_price = bar.get("open", 0)
        if pre_close > 0:
            open_change_pct = (open_price - pre_close) / pre_close * 100
        else:
            open_change_pct = 0.0
        if not _match_condition(open_change_pct, dsl_entry.open_change):
            return False

    if dsl_entry.volume is not None:
        amount = bar.get("amount", 0) or 0
        if not _match_condition(amount, dsl_entry.volume):
            return False

    return True


SENTIMENT_TIERS = {1: "ICE", 2: "COOL", 3: "WARM", 4: "HOT", 5: "FRENZY"}
SENTIMENT_LABELS_TO_LEVEL = {v: k for k, v in SENTIMENT_TIERS.items()}


def _compute_sentiment_level(positive_ratio: float) -> int:
    if positive_ratio < 0.2:
        return 1
    elif positive_ratio < 0.4:
        return 2
    elif positive_ratio < 0.6:
        return 3
    elif positive_ratio < 0.8:
        return 4
    else:
        return 5


def _evaluate_environment(
    date: str,
    dsl_env: Optional[EnvironmentConditions],
    kline_map: dict[str, dict[str, dict]],
) -> bool:
    if dsl_env is None:
        return True

    bars_on_date = [
        code_bars[date] for code_bars in kline_map.values() if date in code_bars
    ]
    if not bars_on_date:
        return True

    if dsl_env.market_change is not None:
        avg_pct_chg = sum(b.get("pct_chg", 0) or 0 for b in bars_on_date) / len(bars_on_date)
        if not _match_condition(avg_pct_chg, dsl_env.market_change):
            return False

    if dsl_env.sentiment is not None:
        positive_count = sum(1 for b in bars_on_date if (b.get("pct_chg", 0) or 0) > 0)
        positive_ratio = positive_count / len(bars_on_date)
        level = _compute_sentiment_level(positive_ratio)
        label = SENTIMENT_TIERS[level]

        if dsl_env.sentiment.eq is not None:
            target = str(dsl_env.sentiment.eq)
            if target in SENTIMENT_LABELS_TO_LEVEL:
                if level != SENTIMENT_LABELS_TO_LEVEL[target]:
                    return False
            else:
                if str(level) != target:
                    return False
        if dsl_env.sentiment.gte is not None:
            target_val = dsl_env.sentiment.gte
            if target_val != int(target_val):
                pass
            if level < target_val:
                return False
        if dsl_env.sentiment.lte is not None:
            target_val = dsl_env.sentiment.lte
            if level > target_val:
                return False

    return True


class BacktestEngine:
    def run(self, dsl: StrategyDSL, years: int = 3) -> BacktestResult:
        klines = _load_klines(years)
        if klines:
            return self._run_real(dsl, klines, years)
        raise BacktestDataUnavailable("真实历史行情不可用，请配置 TUSHARE_TOKEN 或稍后重试")

    def _run_real(self, dsl: StrategyDSL, klines: dict[str, list[dict]], years: int) -> BacktestResult:
        features = {code: _compute_stock_features(code, bars) for code, bars in klines.items()}
        codes = _evaluate_select(dsl.select, klines, features)
        logger.info("entry signal candidates: %d stocks", len(codes))

        tp = dsl.exit.take_profit / 100
        sl = abs(dsl.exit.stop_loss) / 100
        max_hold = dsl.exit.max_hold_days
        per_stock_pct = dsl.position.per_stock
        max_total_pct = dsl.position.max_total
        max_positions = max(1, int(max_total_pct / per_stock_pct)) if per_stock_pct > 0 else 1

        equity = 100.0
        peak = equity
        max_dd = 0.0
        trades: list[dict] = []
        curve: list[dict] = []
        daily_returns: list[float] = []
        total_hold = 0

        all_dates = sorted({bar["date"] for bars in klines.values() for bar in bars})
        if not all_dates:
            raise BacktestDataUnavailable("真实历史行情为空，无法生成回测结果")

        kline_map: dict[str, dict[str, dict]] = {}
        for code, bars in klines.items():
            kline_map[code] = {bar["date"]: bar for bar in bars}

        positions: list[dict] = []
        held_codes: set[str] = set()
        prev_equity = equity

        for i, date in enumerate(all_dates):
            exited: list[int] = []
            for pi, pos in enumerate(positions):
                code = pos["code"]
                bar = kline_map.get(code, {}).get(date)
                if bar:
                    current_price = bar["close"]
                    entry_price = pos["entry_price"]
                    pnl_pct = (current_price - entry_price) / entry_price
                    hold_days = pos["hold_days"] + 1
                    pos["hold_days"] = hold_days

                    should_exit = pnl_pct >= tp or pnl_pct <= -sl or hold_days >= max_hold
                    if should_exit:
                        pnl_value = equity * (per_stock_pct / 100) * pnl_pct
                        equity += pnl_value
                        trades.append({
                            "date": pos["entry_date"],
                            "stock": STOCK_NAMES.get(code, code),
                            "direction": "买入",
                            "hold_days": hold_days,
                            "pnl": round(pnl_pct * 100, 2),
                            "result": "盈利" if pnl_pct > 0 else "亏损",
                        })
                        total_hold += hold_days
                        exited.append(pi)

            for pi in reversed(exited):
                held_codes.discard(positions[pi]["code"])
                positions.pop(pi)

            env_ok = _evaluate_environment(date, dsl.environment, kline_map)
            if env_ok and len(positions) < max_positions:
                for code in codes:
                    if code in held_codes:
                        continue
                    if len(positions) >= max_positions:
                        break
                    bar = kline_map.get(code, {}).get(date)
                    if bar and bar.get("open", 0) > 0 and _evaluate_entry(bar, dsl.entry):
                        positions.append({
                            "code": code,
                            "entry_price": bar["open"],
                            "entry_date": date,
                            "hold_days": 0,
                        })
                        held_codes.add(code)

            entry_count = sum(1 for pos in positions if pos["entry_date"] == date)
            if entry_count > 0:
                logger.debug("date %s: %d new entries, %d total positions", date, entry_count, len(positions))

            if equity != prev_equity or i % 10 == 0:
                curve.append({"date": date, "value": round(equity, 2)})
            daily_ret = (equity - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_returns.append(daily_ret)
            peak = max(peak, equity)
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
            prev_equity = equity

        for pos in positions:
            code = pos["code"]
            last_bars = klines.get(code, [])
            if last_bars:
                pnl_pct = (last_bars[-1]["close"] - pos["entry_price"]) / pos["entry_price"]
                pnl_value = equity * (per_stock_pct / 100) * pnl_pct
                equity += pnl_value
                trades.append({
                    "date": pos["entry_date"],
                    "stock": STOCK_NAMES.get(code, code),
                    "direction": "买入",
                    "hold_days": pos["hold_days"],
                    "pnl": round(pnl_pct * 100, 2),
                    "result": "盈利" if pnl_pct > 0 else "亏损",
                })
                total_hold += pos["hold_days"]

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
