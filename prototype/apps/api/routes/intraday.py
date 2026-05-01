from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from apps.api.auth import require_vip

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


def _maybe_unavailable(client, *, trade_date: str, **extra) -> Optional[dict]:
    """Return wrap_contract unavailable dict iff the facade recorded a sentinel.

    Built once, reused by every short-line handler in this module.
    ``extra`` carries the schema fields the caller would have supplied
    on success (e.g. ``count=0`` / ``rank=[]``) so the unavailable response
    keeps the same shape as the real one.
    """
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        [],
        source="kpl",
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        **extra,
    )


@router.get("/limit-up")
def limit_up_list(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_limit_up(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取涨停列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/broken")
def broken_list(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_broken(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取炸板列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/hot-stocks")
def hot_stocks(date: Optional[str] = Query(None), user: dict = Depends(require_vip("standard"))):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_hot_stocks(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取热股失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/anomaly")
def anomaly(date: Optional[str] = Query(None), user: dict = Depends(require_vip("standard"))):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_market_anomaly(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取异动失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )
