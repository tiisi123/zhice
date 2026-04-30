from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from apps.api.utils.contract import wrap_contract
from packages.features.macro.data import (
    get_macro_indicators,
    get_industry_prosperity,
    get_portfolio,
    compare_industries,
    simulate_rotation,
    get_meso_data,
)

router = APIRouter()


@router.get("/macro")
def macro_panel():
    try:
        indicators = get_macro_indicators()
        sample_mode = any(item.get("data_source") == "mock" for item in indicators)
        return wrap_contract(
            indicators,
            source="static_macro_sample" if sample_mode else "tushare",
            status="mock" if sample_mode else ("real" if indicators else "empty"),
            mock=sample_mode,
            message="TuShare 不可用，当前为静态宏观样例" if sample_mode else "",
            indicators=indicators,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取宏观数据失败: {str(e)}")


@router.get("/prosperity")
def prosperity_heatmap():
    try:
        data = get_industry_prosperity()
        return wrap_contract(
            data,
            source="static_industry_prosperity",
            status="mock" if data else "empty",
            mock=bool(data),
            message="行业景气度为静态样例，真实中观数据待接入",
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
        return wrap_contract(
            compared,
            source="static_industry_prosperity",
            status="mock" if compared else "empty",
            mock=bool(compared),
            message="基于静态行业景气矩阵过滤",
            compared=compared,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"景气度对比失败: {str(e)}")


@router.get("/portfolio")
def portfolio_dashboard():
    try:
        data = get_portfolio()
        total_value = sum(s["market_value"] for s in data)
        total_pnl = sum(s["pnl"] for s in data)
        cost = total_value - total_pnl
        total_pnl_rate = round(total_pnl / cost * 100, 2) if cost > 0 else 0.0
        return wrap_contract(
            data,
            source="sample_portfolio",
            status="mock" if data else "empty",
            mock=bool(data),
            message="当前为示例持仓，真实用户持仓待接入",
            stocks=data,
            total_value=round(total_value, 2),
            total_pnl=round(total_pnl, 2),
            total_pnl_rate=total_pnl_rate,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {str(e)}")


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
