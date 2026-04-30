"""M4A-11 龙虎榜追踪 API。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from packages.connectors.registry import get_kpl
from packages.features.longhu import FAMOUS_SEATS

router = APIRouter()

_kpl = get_kpl()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _match_famous(seat: str) -> str | None:
    for alias, candidates in FAMOUS_SEATS.items():
        for candidate in candidates:
            if candidate in seat or seat in candidate:
                return alias
    return None


def _allocate(rows: list[dict]) -> list[dict]:
    agg: dict[str, dict] = {}
    for row in rows:
        code = row.get("stock_code") or ""
        name = row.get("stock_name") or ""
        net = float(row.get("net_amount") or 0)
        buy_seats = [s for s in row.get("buy_seats", []) if s]
        sell_seats = [s for s in row.get("sell_seats", []) if s]
        t_seats = [s for s in row.get("t_seats", []) if s]

        if net >= 0 and buy_seats:
            amount = net / len(buy_seats)
            for seat in buy_seats:
                item = agg.setdefault(seat, {"seat": seat, "buy": 0.0, "sell": 0.0, "stocks": []})
                item["buy"] += amount
                item["stocks"].append({"code": code, "name": name, "buy": amount, "sell": 0.0})
        if net < 0 and sell_seats:
            amount = abs(net) / len(sell_seats)
            for seat in sell_seats:
                item = agg.setdefault(seat, {"seat": seat, "buy": 0.0, "sell": 0.0, "stocks": []})
                item["sell"] += amount
                item["stocks"].append({"code": code, "name": name, "buy": 0.0, "sell": amount})
        for seat in t_seats:
            item = agg.setdefault(seat, {"seat": seat, "buy": 0.0, "sell": 0.0, "stocks": []})
            item["stocks"].append({"code": code, "name": name, "buy": 0.0, "sell": 0.0})

    rank = []
    for seat, item in agg.items():
        buy = item["buy"]
        sell = item["sell"]
        stocks = item["stocks"]
        rank.append({
            "seat": seat,
            "alias": _match_famous(seat),
            "buy": round(buy, 2),
            "sell": round(sell, 2),
            "net": round(buy - sell, 2),
            "count": len({s["code"] for s in stocks}),
            "stocks": stocks,
        })
    rank.sort(key=lambda x: abs(x["net"]), reverse=True)
    return rank


@router.get("/seats")
def known_seats():
    return {"seats": FAMOUS_SEATS}


@router.get("/rank")
def seat_rank(date: Optional[str] = Query(None), top: int = 20):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        stocks = _kpl.get_longhu_stocks(trade_date) or []
        rank = _allocate(stocks)[:top]
        return {
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "rank": rank,
            "count": len(rank),
            "source": "kpl_longhu_bang",
            "data_status": "ok" if rank else "empty",
            "mock": False,
            "raw_count": len(stocks),
            "note": "席位来自 KPL 龙虎榜接口；买卖金额按股票净买额在同向席位中等分聚合。",
        }
    except Exception as e:
        return {
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "rank": [],
            "count": 0,
            "source": "kpl_longhu_bang",
            "data_status": "unavailable",
            "mock": False,
            "raw_count": 0,
            "message": f"龙虎榜数据失败: {e}",
        }


@router.get("/stock/{code}")
def stock_detail(code: str, date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        rows = [
            r for r in (_kpl.get_longhu_stocks(trade_date) or [])
            if (r.get("stock_code") or "")[:6] == code[:6]
        ]
        return {
            "code": code,
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "rows": rows,
            "count": len(rows),
            "source": "kpl_longhu_bang",
            "data_status": "ok" if rows else "empty",
            "mock": False,
        }
    except Exception as e:
        return {
            "code": code,
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "rows": [],
            "count": 0,
            "source": "kpl_longhu_bang",
            "data_status": "unavailable",
            "mock": False,
            "message": f"查询失败: {e}",
        }
