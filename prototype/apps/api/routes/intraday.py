from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_kpl

router = APIRouter()

_kpl = get_kpl()


@router.get("/limit-up")
def limit_up_list(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_limit_up(trade_date) or []
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
def hot_stocks(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_hot_stocks(trade_date) or []
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
def anomaly(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_market_anomaly(trade_date) or []
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
