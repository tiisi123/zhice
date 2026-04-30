from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from packages.features.macro.data import (
    get_macro_indicators,
    get_industry_prosperity,
    get_portfolio,
    compare_industries,
    simulate_rotation,
    get_meso_data,
)

router = APIRouter()


def _meta(source: str, data_status: str, sample_mode: bool, message: str = "") -> dict:
    return {
        "source": source,
        "data_status": data_status,
        "mock": sample_mode,
        "message": message,
    }


@router.get("/macro")
def macro_panel():
    try:
        indicators = get_macro_indicators()
        sample_mode = any(item.get("data_source") == "mock" for item in indicators)
        return {
            "indicators": indicators,
            **_meta(
                "static_macro_sample" if sample_mode else "tushare",
                "stale" if sample_mode else "ok",
                sample_mode,
                "TuShare 不可用，当前为静态宏观样例" if sample_mode else "",
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取宏观数据失败: {str(e)}")


@router.get("/prosperity")
def prosperity_heatmap():
    try:
        data = get_industry_prosperity()
        sample_mode = True
        return {
            "industries": data,
            "count": len(data),
            **_meta("static_industry_prosperity", "stale", sample_mode, "行业景气度为静态样例，真实中观数据待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取景气度数据失败: {str(e)}")


@router.get("/prosperity/compare")
def prosperity_compare(names: str = Query("半导体,AI/算力,新能源车")):
    try:
        name_list = [n.strip() for n in names.split(",")]
        sample_mode = True
        return {
            "compared": compare_industries(name_list),
            **_meta("static_industry_prosperity", "stale", sample_mode, "基于静态行业景气矩阵过滤"),
        }
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
        return {
            "stocks": data,
            "total_value": round(total_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_rate": total_pnl_rate,
            **_meta("sample_portfolio", "stale", sample_mode := True, "当前为示例持仓，真实用户持仓待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓数据失败: {str(e)}")


@router.get("/meso")
def meso_tracking(industry: Optional[str] = Query(None)):
    try:
        data = get_meso_data(industry)
        sample_mode = True
        return {
            "data": data,
            "count": len(data),
            **_meta("static_meso_indicators", "stale", sample_mode, "中观指标为静态样例，真实价格/订单/库存数据待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取中观数据失败: {str(e)}")


@router.get("/rotation")
def rotation_simulation(source: str = Query("半导体")):
    try:
        targets = simulate_rotation(source)
        sample_mode = True
        return {
            "input_source": source,
            "targets": targets,
            **_meta("static_rotation_rules", "stale", sample_mode, "基于静态映射的轮动规则推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"轮动推演失败: {str(e)}")
