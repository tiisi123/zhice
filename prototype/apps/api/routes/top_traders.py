from __future__ import annotations

from datetime import datetime, timedelta
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


def _candidate_trade_dates(today: str, lookback_days: int = 10) -> list[str]:
    try:
        cursor = datetime.strptime(today, "%Y-%m-%d").date()
    except ValueError:
        return [today]

    dates = [today]
    offset = 1
    while len(dates) < lookback_days and offset <= lookback_days * 2:
        d = cursor - timedelta(days=offset)
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        offset += 1
    return dates


def _latest_trade_date() -> str:
    cursor = datetime.now().date()
    while cursor.weekday() >= 5:
        cursor -= timedelta(days=1)
    return cursor.strftime("%Y-%m-%d")


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
    requested_date = date or _latest_trade_date()
    try:
        raw = []
        trade_date = requested_date
        for candidate in _candidate_trade_dates(requested_date):
            raw = _kpl.get_longhu_stocks(candidate)
            unavail = _maybe_unavailable(_kpl, trade_date=candidate)
            if unavail is not None:
                return unavail
            if raw:
                trade_date = candidate
                break

        unavail = _maybe_unavailable(_kpl, trade_date=trade_date)
        if unavail is not None:
            return unavail

        stocks = build_top_traders(raw or [])
        message = (
            f"{requested_date} 龙虎榜未更新，已展示最近可用交易日 {trade_date}。"
            if stocks and trade_date != requested_date
            else ""
        )

        return wrap_contract(
            stocks,
            source="kpl_longhu_bang",
            status="real" if stocks else "empty",
            message=message,
            trade_date=trade_date,
            requested_date=requested_date,
            count=len(stocks),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl_longhu_bang",
            status="unavailable",
            message=f"获取龙虎榜数据失败: {str(e)}",
            trade_date=requested_date,
            requested_date=requested_date,
            count=0,
        )
