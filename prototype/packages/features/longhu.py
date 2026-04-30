"""M4A-11 龙虎榜特征聚合。"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

# 著名席位（T0 / 一线游资），可持续扩充
FAMOUS_SEATS = {
    "拉萨天团": ["拉萨东环路第二", "拉萨团结路第二", "拉萨金珠西路"],
    "炒股养家": ["华鑫证券上海分公司"],
    "赵老哥": ["国泰君安证券上海江苏路"],
    "方新侠": ["华泰证券深圳益田路荣超商务中心"],
    "章盟主": ["机构专用"],
    "孙哥": ["东方财富证券拉萨团结路"],
    "小鳄鱼": ["中信证券上海漕溪北路"],
}


def build_seat_rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """输入龙虎榜原始行 [{seat, stock_code, stock_name, buy, sell, date}, ...]
    输出席位汇总排序。
    """
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"buy": 0.0, "sell": 0.0, "stocks": [], "net": 0.0, "count": 0}
    )
    for r in rows:
        seat = r.get("seat") or ""
        if not seat:
            continue
        a = agg[seat]
        a["buy"] += float(r.get("buy") or 0)
        a["sell"] += float(r.get("sell") or 0)
        a["count"] += 1
        a["stocks"].append({
            "code": r.get("stock_code"),
            "name": r.get("stock_name"),
            "buy": r.get("buy", 0),
            "sell": r.get("sell", 0),
        })
    result = []
    for seat, v in agg.items():
        net = v["buy"] - v["sell"]
        result.append({
            "seat": seat,
            "alias": _match_famous(seat),
            "buy": v["buy"],
            "sell": v["sell"],
            "net": net,
            "count": v["count"],
            "stocks": v["stocks"][:10],
        })
    result.sort(key=lambda x: x["net"], reverse=True)
    return result


def _match_famous(seat: str) -> str | None:
    for alias, candidates in FAMOUS_SEATS.items():
        for c in candidates:
            if c in seat or seat in c:
                return alias
    return None
