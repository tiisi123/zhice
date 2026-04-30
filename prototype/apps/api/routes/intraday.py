from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from packages.connectors.registry import get_kpl

router = APIRouter()

_kpl = get_kpl()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _pool_response(trade_date: str, data: list[dict], data_status: str = "ok", message: str = "") -> dict:
    return {
        "trade_date": trade_date,
        "updated_at": _now_text(),
        "count": len(data),
        "data": data,
        "mock": False,
        "source": "kpl",
        "data_status": data_status if data else "empty",
        "message": message,
    }


def _unavailable_response(trade_date: str, message: str) -> dict:
    return {
        "trade_date": trade_date,
        "updated_at": _now_text(),
        "count": 0,
        "data": [],
        "mock": False,
        "source": "kpl",
        "data_status": "unavailable",
        "message": message,
    }


@router.get("/limit-up")
def limit_up_list(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_limit_up(trade_date)
        return _pool_response(trade_date, data or [])
    except Exception as e:
        return _unavailable_response(trade_date, f"获取涨停列表失败: {str(e)}")


@router.get("/broken")
def broken_list(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_broken(trade_date)
        return _pool_response(trade_date, data or [])
    except Exception as e:
        return _unavailable_response(trade_date, f"获取炸板列表失败: {str(e)}")


@router.get("/hot-stocks")
def hot_stocks(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_hot_stocks(trade_date)
        return _pool_response(trade_date, data or [])
    except Exception as e:
        return _unavailable_response(trade_date, f"获取热股失败: {str(e)}")


@router.get("/anomaly")
def anomaly(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_market_anomaly(trade_date)
        return _pool_response(trade_date, data or [])
    except Exception as e:
        return _unavailable_response(trade_date, f"获取异动失败: {str(e)}")
