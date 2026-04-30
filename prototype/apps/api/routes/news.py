"""
PRD M2-04 · 热点事件关联（新闻 → 题材 → 个股）
GET /news/flash             7x24 快讯
GET /news/timeline           关联当日 sectors 题材的快讯时间线
POST /news/link-themes       AI：从一段新闻文本里提取受益题材/个股
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_dfcf, get_kpl

logger = logging.getLogger(__name__)
router = APIRouter()
_dfcf = get_dfcf()
_kpl = get_kpl()
_sector_cache: tuple[str, float, list[dict]] | None = None
_SECTOR_CACHE_TTL = 120


@router.get("/flash")
def news_flash(n: int = Query(40, ge=10, le=100)):
    try:
        items = _dfcf.get_news_flash(n=n) or []
    except Exception as e:
        logger.exception("news_flash failed")
        return wrap_contract(
            [],
            source="eastmoney_news",
            status="unavailable",
            message=f"快讯数据获取失败: {e}",
            items=[],
            total=0,
        )
    return wrap_contract(
        items,
        source="eastmoney_news",
        status="real",
        items=items,
        total=len(items),
    )


def _extract_sector_names(sectors: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for s in sectors:
        name = str(s.get("PlateName") or s.get("concept_name") or s.get("name") or "").strip()
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def _get_today_sectors(today: str) -> list[dict]:
    global _sector_cache
    now = time.time()
    if _sector_cache and _sector_cache[0] == today and now - _sector_cache[1] < _SECTOR_CACHE_TTL:
        return _sector_cache[2]
    try:
        sectors = _kpl.get_concept_selected(today) or []
        _sector_cache = (today, now, sectors)
        return sectors
    except Exception:
        logger.warning("get_concept_selected failed", exc_info=True)
        return []


def _normalize_stocks(stocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for s in stocks or []:
        code = str(s.get("code") or s.get("stockCode") or "").strip()
        name = str(s.get("name") or s.get("stockName") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append({"code": code, "name": name})
    return out


@router.get("/timeline")
def news_timeline(
    n: int = Query(60, ge=10, le=200),
    important_only: bool = Query(False, description="仅显示红头/重要快讯"),
):
    """
    抓取最近快讯，并基于关键词与当日题材列表进行关联，返回时间线。
    每条快讯标注：matched_themes（命中的板块名）、matched_stocks（提及的个股）。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        raw = _dfcf.get_news_flash(n=n) or []
    except Exception as e:
        logger.exception("news_timeline flash fetch failed")
        return wrap_contract(
            [],
            source="eastmoney_news",
            status="unavailable",
            message=f"快讯数据获取失败: {e}",
            items=[],
            total=0,
            trade_date=today,
            available_themes=0,
        )
    sectors = _get_today_sectors(today)
    theme_names = _extract_sector_names(sectors)
    # 简单子串匹配：题材名出现在 title 或 summary 中即视为相关
    items: list[dict] = []
    for n0 in raw:
        if important_only and not n0.get("is_red"):
            continue
        text = f"{n0.get('title', '')} {n0.get('summary', '')}"
        matched_themes = [t for t in theme_names if t in text]
        matched_stocks = _normalize_stocks(n0.get("stocks") or [])
        items.append({
            **n0,
            "matched_themes": matched_themes[:6],
            "matched_stocks": matched_stocks[:8],
            "stocks": matched_stocks[:8],
        })
    return wrap_contract(
        items,
        source="eastmoney_news",
        status="real",
        items=items,
        total=len(items),
        trade_date=today,
        available_themes=len(theme_names),
    )


# ============== AI：从新闻文本反查受益题材/个股 ==============
class LinkIn(BaseModel):
    text: str = Field(..., min_length=10, description="新闻/政策文本")


@router.post("/link-themes")
def link_themes(inp: LinkIn):
    """
    给一段新闻/政策文本，让 AI 推断：
      - 受益题材（板块名）
      - 受益个股（A 股 6 位代码）
      - 利好程度（强/中/弱）
      - 时滞（即时/短期/中期）
    输出 JSON 友好的 Markdown。
    """
    from apps.ai.agents.llm_client import llm

    today = datetime.now().strftime("%Y-%m-%d")
    sectors = _get_today_sectors(today)
    theme_names = _extract_sector_names(sectors)[:60]
    news_text = inp.text.strip()[:3000]

    prompt = f"""你是一位短线题材分析师，请从下面新闻中提取与 A 股相关的受益题材与个股。

【可参考的当日活跃题材】
{', '.join(theme_names) if theme_names else '（暂无数据）'}

【新闻原文】
{news_text}

请按以下结构输出 Markdown：

## 1. 核心信息
（一句话总结新闻关键事实）

## 2. 受益题材（≤5）
- 题材名 | 利好强度 | 时滞 | 简短理由

## 3. 受益个股（≤8）
- 代码 名称 | 关联题材 | 简短理由
（仅给出 A 股 6 位代码；不确定的不要乱编）

## 4. 风险与不确定性
（2-3 行）

## 5. 操作倾向
（一句话：建议如何参与，含止损位）

注意：
- 题材名优先从【可参考的当日活跃题材】中选择，能直接命中盘面热点
- 个股代码必须是真实存在的 A 股；如无把握，宁缺毋滥
"""
    try:
        text = llm.chat(prompt)
        return {
            "analysis": text,
            "theme_pool": theme_names,
            "disclaimer": "AI 推断仅供参考，不构成投资建议。",
        }
    except Exception as e:
        logger.exception("link_themes failed")
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {e}")
