"""研究/基本面扩展接口：公告 / AI 财报解读 / 另类数据 / 卖方预期时间线 / 历史景气周期。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from packages.features.research_ext import (
    list_announcements,
    interpret_financial,
    list_alt_data,
    sellside_timeline,
    historical_prosperity,
)
from packages.features.valuation import get_financial

router = APIRouter()


def _meta(source: str, data_status: str, sample_mode: bool, message: str = "") -> dict:
    return {
        "source": source,
        "data_status": data_status,
        "mock": sample_mode,
        "message": message,
    }


@router.get("/announcements")
def announcements(days: int = Query(7, ge=1, le=30), kind: str | None = None):
    try:
        items = list_announcements(days, kind)
        sample_mode = True
        return {
            "days": days,
            "items": items,
            "count": len(items),
            **_meta("sample_research_announcements", "stale", sample_mode, "研究中心公告为生成样例，真实公告请优先使用 /finance/announcements/{code}"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取公告失败: {e}")


@router.get("/interpret/{code}")
def interpret(code: str):
    try:
        fin = get_financial(code)
        if not fin:
            raise HTTPException(status_code=404, detail=f"暂无 {code} 的财务数据")
        source = fin.get("data_source") or "unknown"
        sample_mode = source == "mock"
        return {
            "code": code,
            "data": interpret_financial(code, fin),
            **_meta(
                "sample_financials+interpret_rule" if sample_mode else f"{source}+interpret_rule",
                "stale" if sample_mode else "ok",
                sample_mode,
                "财报解读为规则推演，基础财务可能来自样例" if sample_mode else "财报解读为规则推演",
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"财报解读失败: {e}")


@router.get("/alt-data")
def alt_data(industry: str | None = None):
    try:
        items = list_alt_data(industry)
        sample_mode = True
        return {
            "industry": industry,
            "items": items,
            "count": len(items),
            **_meta("sample_research_alt_data", "stale", sample_mode, "另类数据为静态样例，真实源待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取另类数据失败: {e}")


@router.get("/sellside/{code}")
def sellside(code: str):
    try:
        timeline = sellside_timeline(code)
        sample_mode = True
        return {
            "code": code,
            "timeline": timeline,
            "count": len(timeline),
            **_meta("sample_sellside_timeline", "stale", sample_mode, "卖方预期时间线为规则生成样例"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取卖方预期失败: {e}")


@router.get("/prosperity-cycle")
def prosperity_cycle(industry: str = Query(...)):
    try:
        sample_mode = True
        return {
            **historical_prosperity(industry),
            **_meta("sample_historical_prosperity", "stale", sample_mode, "历史景气周期为模拟序列，真实历史中观数据待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"历史景气周期失败: {e}")
