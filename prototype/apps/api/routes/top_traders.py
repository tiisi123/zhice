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
from packages.features.longhu import build_top_traders

router = APIRouter()

_kpl = get_kpl()


def _maybe_unavailable(client, *, trade_date: str, **extra) -> Optional[dict]:
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        [],
        source="kpl_longhu_bang",
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        count=0,
        **extra,
    )


@router.get("/top-traders")
def top_traders(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        raw = _kpl.get_longhu_stocks(trade_date)

        unavail = _maybe_unavailable(_kpl, trade_date=trade_date)
        if unavail is not None:
            return unavail

        stocks = build_top_traders(raw or [])

        return wrap_contract(
            stocks,
            source="kpl_longhu_bang",
            status="real" if stocks else "empty",
            trade_date=trade_date,
            count=len(stocks),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl_longhu_bang",
            status="unavailable",
            message=f"获取龙虎榜数据失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )
