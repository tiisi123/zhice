from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from apps.api.auth import consume_quota
from apps.api.db import execute
from packages.connectors.registry import get_kpl
from packages.features.market import build_market_summary
from apps.ai.agents.agents import (
    MarketReplayAgent,
    StockInsightAgent,
    HotThemeAgent,
    StrategyBuilderAgent,
    BacktestAnalystAgent,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_kpl = get_kpl()

_CACHE_MAX = 64

class _LRUCache(OrderedDict):
    def get_or_none(self, key: str) -> str | None:
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put(self, key: str, value: str) -> None:
        self[key] = value
        self.move_to_end(key)
        while len(self) > _CACHE_MAX:
            self.popitem(last=False)

_headline_cache = _LRUCache()
_replay_agent = MarketReplayAgent()
_stock_agent = StockInsightAgent()
_theme_agent = HotThemeAgent()
_strategy_agent = StrategyBuilderAgent()
_backtest_agent = BacktestAnalystAgent()


@router.get("/headline")
def headline(date: Optional[str] = Query(None)):
    """AI 一句话速报（无需 quota，内存缓存按日去重）。"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    cached = _headline_cache.get_or_none(trade_date)
    if cached is not None:
        return {"trade_date": trade_date, "headline": cached}
    try:
        kpl_stats = _kpl.get_market_statistics(trade_date)
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        sectors = _kpl.get_concept_selected(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date

        from apps.ai.context_builders.market_context import build_market_context
        from apps.ai.prompts.templates import MARKET_HEADLINE
        from apps.ai.agents.llm_client import llm

        context = build_market_context(summary, limit_up, broken, sectors)
        text = llm.chat(MARKET_HEADLINE.format(context=context))
        text = text.strip().strip("「」""''")
        _headline_cache.put(trade_date, text)
        return {"trade_date": trade_date, "headline": text}
    except Exception:
        sent = "—"
        try:
            kpl_stats = _kpl.get_market_statistics(trade_date)
            limit_up = _kpl.get_limit_up(trade_date)
            broken = _kpl.get_broken(trade_date)
            s = build_market_summary(kpl_stats, limit_up, broken)
            top_sector = ""
            sectors = _kpl.get_concept_selected(trade_date)
            if sectors:
                top_sector = (sectors[0].get("PlateName") or sectors[0].get("concept_name") or "")
            sent = s.get("sentiment_level", "中性")
            text = f"{sent}，涨停{s.get('limit_up_count',0)}家，最高{s.get('max_board',0)}板"
            if top_sector:
                text += f"，{top_sector}领涨"
            _headline_cache.put(trade_date, text)
            return {"trade_date": trade_date, "headline": text}
        except Exception:
            return {"trade_date": trade_date, "headline": ""}


@router.get("/replay-report")
def replay_report(date: Optional[str] = Query(None), user: dict = Depends(consume_quota("ai_report"))):
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        kpl_stats = _kpl.get_market_statistics(trade_date)
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        sectors = _kpl.get_concept_selected(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date
        report = _replay_agent.generate_report(summary, limit_up, broken, sectors)
        # 自动归档
        try:
            execute(
                "INSERT INTO reports_archive(author_id, author_name, trade_date, kind, title, content, summary) VALUES (?,?,?,?,?,?,?)",
                (
                    user["id"],
                    user.get("nickname") or "智策官方",
                    trade_date,
                    "replay",
                    f"{trade_date} 收盘复盘",
                    report,
                    f"涨停{summary.get('limit_up_count',0)} 炸板{summary.get('broken_count',0)} 情绪{summary.get('sentiment_level','')}",
                ),
            )
        except Exception:
            pass
        return {"trade_date": trade_date, "summary": summary, "report": report}
    except HTTPException:
        raise
    except Exception:
        logger.exception("生成复盘报告失败")
        raise HTTPException(status_code=500, detail="生成复盘报告失败，请稍后重试")


@router.get("/stock-insight/{code}")
def stock_insight(code: str, date: Optional[str] = Query(None)):
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        # 从涨停池/炸板池/热股中查找真实数据
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        hot = _kpl.get_hot_stocks(trade_date)

        stock = None
        for pool in [limit_up, broken, hot]:
            for s in pool:
                if s.get("stock_code", "")[:6] == code[:6]:
                    stock = s
                    break
            if stock:
                break

        if not stock:
            return {
                "code": code,
                "name": code,
                "report": "",
                "source": "kpl",
                "data_status": "empty",
                "message": "该股票不在真实涨停/炸板/热股池中，暂不生成短线洞察",
            }

        themes = stock.get("related_plates", [])
        if not themes and stock.get("first_plate_name"):
            themes = [stock["first_plate_name"]]

        report = _stock_agent.generate_summary(stock, themes)
        return {"code": code, "name": stock.get("stock_name", code), "report": report, "source": "kpl", "data_status": "ok"}
    except Exception:
        logger.exception("生成个股洞察失败: %s", code)
        raise HTTPException(status_code=500, detail="生成个股洞察失败，请稍后重试")


@router.get("/theme-analysis/{theme_name}")
def theme_analysis(theme_name: str, date: Optional[str] = Query(None)):
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        # 获取涨停池中该题材关联的股票
        limit_up = _kpl.get_limit_up(trade_date)
        related_stocks = [
            s for s in limit_up
            if theme_name in s.get("first_plate_name", "")
            or theme_name in s.get("reason", "")
            or theme_name in ",".join(s.get("related_plates", []))
        ]
        report = _theme_agent.analyze_theme(theme_name, related_stocks)
        return {"theme": theme_name, "stock_count": len(related_stocks), "report": report}
    except Exception:
        logger.exception("生成题材分析失败: %s", theme_name)
        raise HTTPException(status_code=500, detail="生成题材分析失败，请稍后重试")


class StrategyInput(BaseModel):
    text: str


@router.post("/strategy-dsl")
def strategy_dsl(inp: StrategyInput):
    try:
        dsl_text = _strategy_agent.natural_language_to_dsl(inp.text)
        return {"input": inp.text, "dsl": dsl_text}
    except Exception:
        logger.exception("策略生成失败")
        raise HTTPException(status_code=500, detail="策略生成失败，请稍后重试")


class ChatInput(BaseModel):
    message: str
    history: list[dict] = []


@router.post("/chat")
def ai_chat(inp: ChatInput, _user: dict = Depends(consume_quota("ai_chat"))):
    try:
        from apps.ai.agents.llm_client import llm
        # 构建包含历史的对话上下文
        context = ""
        for msg in inp.history[-6:]:
            role = "用户" if msg.get("role") == "user" else "AI"
            context += f"{role}: {msg.get('content', '')}\n"
        prompt = f"{context}用户: {inp.message}" if context else inp.message
        response = llm.chat(prompt)
        return {"message": inp.message, "response": response}
    except Exception:
        logger.exception("AI对话失败")
        raise HTTPException(status_code=500, detail="AI对话失败，请稍后重试")
