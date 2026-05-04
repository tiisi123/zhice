from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from apps.api.utils.contract import wrap_contract
from packages.connectors.kpl.sentinel import (
    cookie_unavailable_message,
    from_client_state,
    is_cookie_missing,
    is_upstream_error,
)
from packages.connectors.registry import get_kpl

router = APIRouter()

_kpl = get_kpl()


def _maybe_unavailable(client, *, trade_date: str, body=None, **extra) -> Optional[dict]:
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        {} if body is None else body,
        source="kpl",
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        **extra,
    )


def _extract_stock(raw: dict) -> dict:
    return {
        "stock_code": raw.get("stock_code", ""),
        "stock_name": raw.get("stock_name", ""),
        "price": raw.get("price", 0.0),
        "change_rate": raw.get("change_rate", 0.0),
        "limit_time": raw.get("first_limit_time") or raw.get("time", ""),
        "seal_amount": raw.get("seal_amount", 0.0),
        "board_count": raw.get("board_count", 0),
        "sectors": raw.get("related_plates") or (
            [raw["first_plate_name"]] if raw.get("first_plate_name") else []
        ),
    }


@router.get("/board-replay")
def board_replay(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)

        unavail = _maybe_unavailable(
            _kpl, trade_date=trade_date,
            first_board=[], consecutive=[], broken=[],
        )
        if unavail is not None:
            return unavail

        first_board = []
        consecutive = []
        for stock in (limit_up or []):
            item = _extract_stock(stock)
            if item["board_count"] >= 2:
                consecutive.append(item)
            else:
                first_board.append(item)

        broken_list = [_extract_stock(s) for s in (broken or [])]

        data = {
            "first_board": first_board,
            "consecutive": consecutive,
            "broken": broken_list,
        }
        total = len(first_board) + len(consecutive) + len(broken_list)

        return wrap_contract(
            data,
            source="kpl",
            status="real" if total else "empty",
            trade_date=trade_date,
            total=total,
        )
    except Exception as e:
        return wrap_contract(
            {"first_board": [], "consecutive": [], "broken": []},
            source="kpl",
            status="unavailable",
            message=f"获取涨停复盘失败: {str(e)}",
            trade_date=trade_date,
            total=0,
        )
