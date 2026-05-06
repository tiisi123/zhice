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


def _status_from_modes(items: list[dict], *, sample_source: str, real_source: str) -> tuple[str, str, bool, str, str, str]:
    if not items:
        return real_source, "empty", False, "", "empty", ""

    modes = {str(item.get("data_mode") or "") for item in items}
    as_of = max((str(item.get("as_of") or item.get("date") or "") for item in items), default="")
    reasons = sorted({str(item.get("fallback_reason") or "") for item in items if item.get("fallback_reason")})

    if modes and modes <= {"sample"}:
        return sample_source, "mock", True, "当前为静态样例，真实数据源不可用或未返回有效数据", "sample", reasons[0] if reasons else ""
    if "live" in modes and modes <= {"live"}:
        return real_source, "real", False, "", "live", ""
    if "live" in modes:
        reason = reasons[0] if reasons else "partial_static_reference"
        return f"{real_source}+static_reference", "fallback", False, "部分指标来自静态参考值，请结合来源标识使用", "hybrid", reason
    if "static" in modes:
        reason = reasons[0] if reasons else "static_reference_only"
        return sample_source, "fallback", False, "当前为静态参考值，未完全接入实时源", "static", reason
    return sample_source, "mock", True, "当前为静态样例，真实数据源不可用或未返回有效数据", "sample", reasons[0] if reasons else ""


@router.get("/macro")
def macro_panel():
    try:
        indicators = get_macro_indicators()
        source, status, mock, message, data_mode, fallback_reason = _status_from_modes(
            indicators,
            sample_source="static_macro_sample",
            real_source="tushare_macro",
        )
        as_of = max((str(item.get("as_of") or item.get("date") or "") for item in indicators), default="")
        return wrap_contract(
            indicators,
            source=source,
            status=status,
            mock=mock,
            message=message,
            data_source=source,
            data_mode=data_mode,
            as_of=as_of,
            fallback_reason=fallback_reason,
            indicators=indicators,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取宏观数据失败: {str(e)}")


@router.get("/prosperity")
def prosperity_heatmap():
    try:
        data = get_industry_prosperity()
        source, status, mock, message, data_mode, fallback_reason = _status_from_modes(
            data,
            sample_source="static_industry_prosperity",
            real_source="tushare_sw_daily",
        )
        as_of = max((str(item.get("as_of") or "") for item in data), default="")
        return wrap_contract(
            data,
            source=source,
            status=status,
            mock=mock,
            message=message,
            data_source=source,
            data_mode=data_mode,
            as_of=as_of,
            fallback_reason=fallback_reason,
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
        source, status, mock, message, data_mode, fallback_reason = _status_from_modes(
            compared,
            sample_source="static_industry_prosperity",
            real_source="tushare_sw_daily",
        )
        as_of = max((str(item.get("as_of") or "") for item in compared), default="")
        return wrap_contract(
            compared,
            source=source,
            status=status,
            mock=mock,
            message=message,
            data_source=source,
            data_mode=data_mode,
            as_of=as_of,
            fallback_reason=fallback_reason,
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
