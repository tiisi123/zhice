from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException

from apps.api.auth.deps import current_user
from apps.api.db import query_all
from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_dfcf
from packages.features.macro.data import (
    get_macro_indicators,
    get_industry_prosperity,
    compare_industries,
    simulate_rotation,
    get_meso_data,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/macro")
def macro_panel():
    try:
        indicators = get_macro_indicators()
        has_real = any(item.get("data_source") == "tushare" for item in indicators)
        all_mock = all(item.get("data_source") == "mock" for item in indicators)
        if all_mock:
            source, status, mock = "static_macro_sample", "mock", True
            message = "TuShare 不可用，当前为静态宏观样例"
        elif has_real:
            source, status, mock = "tushare", "real", False
            message = ""
        else:
            source, status, mock = "static_macro_sample", "empty", False
            message = ""
        return wrap_contract(
            indicators,
            source=source,
            status=status,
            mock=mock,
            message=message,
            indicators=indicators,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取宏观数据失败: {str(e)}")


@router.get("/prosperity")
def prosperity_heatmap():
    try:
        data = get_industry_prosperity()
        has_real = any(item.get("data_source") == "tushare" for item in data)
        if has_real:
            source, status, mock = "tushare+sw_index", "real", False
            message = ""
        else:
            source, status, mock = "static_industry_prosperity", "mock", True
            message = "行业景气度为静态样例，真实中观数据待接入"
        return wrap_contract(
            data,
            source=source,
            status=status if data else "empty",
            mock=mock,
            message=message,
            industries=data,
            count=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取景气度数据失败: {str(e)}")


@router.get("/prosperity/compare")
def prosperity_compare(names: str = Query("半导体,AI/算力,新能源车")):
    try:
        name_list = [n.strip() for n in names.split(",")]
        compared = compare_industries(name_list)
        has_real = any(item.get("data_source") == "tushare" for item in compared)
        if has_real:
            source, status, mock = "tushare+sw_index", "real", False
            message = ""
        else:
            source, status, mock = "static_industry_prosperity", "mock", True
            message = "基于静态行业景气矩阵过滤"
        return wrap_contract(
            compared,
            source=source,
            status=status if compared else "empty",
            mock=mock,
            message=message,
            compared=compared,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"景气度对比失败: {str(e)}")


@router.get("/portfolio")
def portfolio_dashboard(user: dict = Depends(current_user)):
    rows = query_all(
        "SELECT code, name, cost_price, shares FROM watchlist "
        "WHERE user_id=? AND cost_price IS NOT NULL",
        (user["id"],),
    )
    if not rows:
        return wrap_contract(
            [],
            source="user_watchlist",
            status="empty",
            mock=False,
            stocks=[],
            total_value=0,
            total_pnl=0,
            total_pnl_rate=0,
        )

    dfcf = get_dfcf()
    stocks = []
    quote_ok = 0
    for row in rows:
        code, name = row["code"], row["name"]
        cost_price, shares = row["cost_price"], row["shares"] or 0
        current_price = None
        try:
            quote = dfcf.get_quote(code)
            if "error" not in quote:
                current_price = quote.get("price")
                quote_ok += 1
            else:
                logger.warning("DFCF quote error for %s: %s", code, quote["error"])
        except Exception as exc:
            logger.warning("DFCF quote fetch failed for %s: %s", code, exc)

        if current_price is not None:
            market_value = round(current_price * shares, 2)
            cost_basis = round(cost_price * shares, 2)
            pnl = round(market_value - cost_basis, 2)
            pnl_rate = round(pnl / cost_basis * 100, 2) if cost_basis > 0 else 0.0
        else:
            market_value = None
            cost_basis = round(cost_price * shares, 2)
            pnl = None
            pnl_rate = None

        stocks.append({
            "code": code,
            "name": name,
            "cost_price": cost_price,
            "shares": shares,
            "current_price": current_price,
            "market_value": market_value,
            "pnl": pnl,
            "pnl_rate": pnl_rate,
        })

    valued = [s for s in stocks if s["market_value"] is not None]
    total_value = round(sum(s["market_value"] for s in valued), 2)
    total_cost = sum(s["cost_price"] * s["shares"] for s in valued)
    total_pnl = round(total_value - total_cost, 2)
    total_pnl_rate = round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0.0

    if quote_ok > 0:
        status = "real"
    else:
        status = "unavailable"

    logger.info("portfolio: %d positions, %d quotes ok", len(rows), quote_ok)

    return wrap_contract(
        stocks,
        source="dfcf",
        status=status,
        mock=False,
        stocks=stocks,
        total_value=total_value,
        total_pnl=total_pnl,
        total_pnl_rate=total_pnl_rate,
    )


@router.get("/meso")
def meso_tracking(industry: Optional[str] = Query(None)):
    try:
        data = get_meso_data(industry)
        return wrap_contract(
            data,
            source="static_meso_indicators",
            status="mock" if data else "empty",
            mock=bool(data),
            message="中观指标为静态样例，真实价格/订单/库存数据待接入",
            count=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取中观数据失败: {str(e)}")


@router.get("/rotation")
def rotation_simulation(source: str = Query("半导体")):
    try:
        targets = simulate_rotation(source)
        return wrap_contract(
            targets,
            source="static_rotation_rules",
            status="mock" if targets else "empty",
            mock=bool(targets),
            message="基于静态映射的轮动规则推演",
            input_source=source,
            targets=targets,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轮动推演失败: {str(e)}")
