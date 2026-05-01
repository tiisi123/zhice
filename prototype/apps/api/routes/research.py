"""研究/基本面扩展接口：公告 / AI 财报解读 / 另类数据 / 卖方预期时间线 / 历史景气周期。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.auth import require_vip

from apps.api.utils.contract import wrap_contract
from packages.features.research_ext import (
    list_announcements,
    interpret_financial,
    list_alt_data,
    sellside_timeline,
    historical_prosperity,
)
from packages.features.valuation import get_financial

router = APIRouter()


@router.get("/announcements")
def announcements(days: int = Query(7, ge=1, le=30), kind: str | None = None):
    try:
        items = list_announcements(days, kind)
        return wrap_contract(
            items,
            source="sample_research_announcements",
            status="mock" if items else "empty",
            mock=bool(items),
            message="研究中心公告为生成样例，真实公告请优先使用 /finance/announcements/{code}",
            days=days,
            items=items,
            count=len(items),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取公告失败: {e}")


@router.get("/interpret/{code}")
def interpret(code: str):
    try:
        fin = get_financial(code)
        if not fin:
            raise HTTPException(status_code=404, detail=f"暂无 {code} 的财务数据")
        src = fin.get("data_source") or "unknown"
        sample_mode = src == "mock"
        interpretation = interpret_financial(code, fin)
        return wrap_contract(
            interpretation,
            source="sample_financials+interpret_rule" if sample_mode else f"{src}+interpret_rule",
            status="mock" if sample_mode else "real",
            mock=sample_mode,
            message="财报解读为规则推演，基础财务可能来自样例" if sample_mode else "财报解读为规则推演",
            code=code,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"财报解读失败: {e}")


@router.get("/alt-data")
def alt_data(industry: str | None = None):
    try:
        items = list_alt_data(industry)
        return wrap_contract(
            items,
            source="sample_research_alt_data",
            status="mock" if items else "empty",
            mock=bool(items),
            message="另类数据为静态样例，真实源待接入",
            industry=industry,
            items=items,
            count=len(items),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取另类数据失败: {e}")


@router.get("/sellside/{code}")
def sellside(code: str):
    try:
        timeline = sellside_timeline(code)
        return wrap_contract(
            timeline,
            source="sample_sellside_timeline",
            status="mock" if timeline else "empty",
            mock=bool(timeline),
            message="卖方预期时间线为规则生成样例",
            code=code,
            timeline=timeline,
            count=len(timeline),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取卖方预期失败: {e}")


@router.get("/prosperity-cycle")
def prosperity_cycle(industry: str = Query(...), user: dict = Depends(require_vip("standard"))):
    try:
        result = historical_prosperity(industry)
        sample_mode = True  # sample_historical_prosperity 为静态模拟序列
        extras = {
            k: v for k, v in result.items()
            if k not in ("source", "data_status", "mock", "message", "updated_at")
        }
        return wrap_contract(
            result,
            source="sample_historical_prosperity",
            status="mock",
            mock=sample_mode,
            message="历史景气周期为模拟序列，真实历史中观数据待接入",
            **extras,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"历史景气周期失败: {e}")
