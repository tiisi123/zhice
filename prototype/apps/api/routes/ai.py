from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from apps.api.auth import consume_quota
from apps.api.db import execute
from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_kpl
from packages.features.market import build_market_summary
from apps.ai.agents.agents import (
    MarketReplayAgent,
    StockInsightAgent,
    HotThemeAgent,
    StrategyBuilderAgent,
    BacktestAnalystAgent,
    BoardTradingAgent,
    EtfRotationAgent,
)
from apps.ai.context_builders.copilot_orchestrator import (
    build_copilot_evidence,
    build_theme_stocks,
    format_copilot_evidence,
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
_board_trading_agent = BoardTradingAgent()
_etf_rotation_agent = EtfRotationAgent()


@router.get("/headline")
def headline(date: Optional[str] = Query(None)):
    """AI 一句话速报（无需 quota，内存缓存按日去重）。"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    cached = _headline_cache.get_or_none(trade_date)
    if cached is not None:
        return wrap_contract(
            cached,
            source="kpl+llm",
            status="real",
            trade_date=trade_date,
            headline=cached,
        )
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
        text = llm.fast_chat(MARKET_HEADLINE.format(context=context))
        text = text.strip().strip("「」""''")
        _headline_cache.put(trade_date, text)
        return wrap_contract(
            text,
            source="kpl+llm",
            status="real",
            trade_date=trade_date,
            headline=text,
        )
    except Exception:
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
            return wrap_contract(
                text,
                source="kpl",
                status="fallback",
                message="LLM 不可用，已降级为 KPL 规则速报",
                trade_date=trade_date,
                headline=text,
            )
        except Exception:
            return wrap_contract(
                "",
                source="kpl",
                status="unavailable",
                message="KPL/LLM 均不可用",
                trade_date=trade_date,
                headline="",
            )


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
        return wrap_contract(
            report,
            source="kpl+llm",
            status="real",
            trade_date=trade_date,
            summary=summary,
            report=report,
        )
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
            return wrap_contract(
                {},
                source="kpl",
                status="empty",
                message="该股票不在真实涨停/炸板/热股池中，暂不生成短线洞察",
                code=code,
                name=code,
                report="",
            )

        themes = stock.get("related_plates", [])
        if not themes and stock.get("first_plate_name"):
            themes = [stock["first_plate_name"]]

        report = _stock_agent.generate_summary(stock, themes)
        return wrap_contract(
            {"code": code, "name": stock.get("stock_name", code), "report": report},
            source="kpl",
            status="real",
            code=code,
            name=stock.get("stock_name", code),
            report=report,
        )
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
    current_page: Optional[str] = None
    trade_date: Optional[str] = None


PAGE_CONTEXTS = {
    "/replay": {
        "label": "收盘复盘",
        "apis": [
            "GET /api/market/summary",
            "GET /api/market/ladder",
            "GET /api/market/sectors",
            "GET /api/market/capital-flow",
            "GET /api/market/next-day-strategy",
        ],
    },
    "/theme": {
        "label": "题材板块",
        "apis": ["GET /api/market/sectors", "GET /api/theme/*", "GET /api/ai/theme-analysis/{theme_name}"],
    },
    "/intraday": {
        "label": "盘中盯盘",
        "apis": ["GET /api/intraday/*", "GET /api/market/sectors", "GET /api/market/summary"],
    },
    "/etf-rotation": {
        "label": "ETF轮动",
        "apis": ["GET /api/etf/rotation/dashboard", "POST /api/ai/agent/etf-rotation"],
    },
    "/value": {
        "label": "价值/持仓",
        "apis": ["GET /api/value/*", "GET /api/finance/*"],
    },
    "/growth": {
        "label": "成长景气",
        "apis": ["GET /api/growth/*"],
    },
}


def _page_context(current_page: Optional[str]) -> dict:
    page = current_page or ""
    for prefix, ctx in PAGE_CONTEXTS.items():
        if page.startswith(prefix):
            return ctx
    return {
        "label": page or "全局工作台",
        "apis": ["GET /api/market/summary", "GET /api/market/sectors"],
    }


def _build_chat_market_context(trade_date: str) -> tuple[str, list[str]]:
    sources = [
        "GET /api/market/summary",
        "GET /api/market/ladder",
        "GET /api/market/sectors",
        "KPL: market_statistics / limit_up / broken / concept_selected",
    ]
    try:
        kpl_stats = _kpl.get_market_statistics(trade_date)
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        sectors = _kpl.get_concept_selected(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date

        from apps.ai.context_builders.market_context import build_market_context

        context = build_market_context(summary, limit_up, broken, sectors)
        return context, sources
    except Exception:
        logger.warning("AI chat market context unavailable", exc_info=True)
        return f"## 市场数据\n- trade_date: {trade_date}\n- KPL 核心市场上下文暂不可用，回答需明确提示数据缺口。", sources


@router.get("/theme-stocks")
def ai_theme_stocks(theme: str = Query(..., min_length=1, max_length=50), date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = build_theme_stocks(theme, trade_date)
        return wrap_contract(
            data,
            source="kpl",
            status="real" if data.get("limit_up_stocks") or data.get("broken_stocks") else "empty",
            trade_date=trade_date,
            theme=theme,
            count=data.get("limit_up_count", 0),
        )
    except Exception:
        logger.exception("AI theme stocks failed: %s", theme)
        return wrap_contract(
            {},
            source="kpl",
            status="unavailable",
            message="题材股票明细获取失败",
            trade_date=trade_date,
            theme=theme,
            count=0,
        )


@router.post("/chat")
def ai_chat(inp: ChatInput, _user: dict = Depends(consume_quota("ai_chat"))):
    try:
        from apps.ai.agents.llm_client import llm
        trade_date = inp.trade_date or datetime.now().strftime("%Y-%m-%d")
        page_ctx = _page_context(inp.current_page)
        market_context, context_sources = _build_chat_market_context(trade_date)
        evidence = build_copilot_evidence(inp.message, inp.current_page, trade_date)
        evidence_text = format_copilot_evidence(evidence)
        context_sources = list(dict.fromkeys([*page_ctx["apis"], *context_sources, *evidence.get("sources", [])]))

        # 构建包含历史的对话上下文
        history_text = ""
        for msg in inp.history[-6:]:
            role = "用户" if msg.get("role") == "user" else "AI"
            history_text += f"{role}: {msg.get('content', '')}\n"
        prompt = f"""
你是智策 AI Copilot，请用中文回答用户问题。你需要像一个投研团队一样组织答案：

1. 策略分析师：先给结论、可跟踪方向、风险边界和次日验证点。
2. 数据分析师：解释结论来自哪些数据，指出样本口径、实时性和缺口。
3. 风控分析师：提示不确定性，不给确定收益承诺，不构成投资建议。

当前页面：{page_ctx["label"]}
当前页面可用 API：{"、".join(page_ctx["apis"])}
全局可补充 API：GET /api/market/summary、GET /api/market/ladder、GET /api/market/sectors、GET /api/market/capital-flow、GET /api/market/next-day-strategy
子页面数据规则：你不能直接读取前端隐藏组件的本地状态；但只要对应后端 API 已知，就可以基于这些 API 的全局/页面上下文回答跨板块问题。
连续追问规则：结合最近 6 轮历史回答，不要丢失用户上一轮限定条件。
数据时间：{trade_date}。AI 速报和本次短线上下文默认使用当日 KPL 实时/收盘口径数据；若用户询问历史日，则以传入日期为准。
回答约束：
- 如果用户追问“某题材的 N 只票”，必须先使用下方 evidence.theme_stocks 里的股票明细逐只分析。
- 如果 evidence.theme_stocks 为空，不要编造股票名单；请明确说当前 API 未匹配到题材成分股，并建议用户换题材名或补充股票代码。
- 不允许输出“买入/卖出/满仓”等指令；用“关注/观察/回避/等待确认/风险边界”表达。

{market_context}

结构化证据包：
{evidence_text}

最近对话：
{history_text if history_text else "无"}

用户问题：
{inp.message}
"""
        response = llm.chat(prompt)
        return {
            "message": inp.message,
            "response": response,
            "context_sources": context_sources,
            "evidence": evidence,
            "trade_date": trade_date,
        }
    except Exception:
        logger.exception("AI对话失败")
        raise HTTPException(status_code=500, detail="AI对话失败，请稍后重试")


class BoardTradingInput(BaseModel):
    style: str = "均衡"
    risk_preference: str = "中等"
    focus_sectors: list[str] = []


@router.post("/agent/board-trading")
def agent_board_trading(inp: BoardTradingInput):
    user_style = f"风格: {inp.style}\n风险偏好: {inp.risk_preference}"
    if inp.focus_sectors:
        user_style += f"\n关注板块: {'、'.join(inp.focus_sectors)}"
    try:
        trade_date = datetime.now().strftime("%Y-%m-%d")
        board_replay = {}
        ladder = {}
        top_traders_data: list[dict] = []
        backtest_data = None
        data_source = "kpl+llm"

        try:
            limit_up = _kpl.get_limit_up(trade_date)
            broken = _kpl.get_broken(trade_date)
            first_board = [s for s in limit_up if (s.get("board_count") or 1) == 1]
            consecutive = [s for s in limit_up if (s.get("board_count") or 1) >= 2]
            board_replay = {"first_board": first_board, "consecutive": consecutive, "broken": broken}
        except Exception:
            logger.warning("打板Agent: 涨停复盘数据获取失败，使用空数据")

        try:
            from apps.api.routes.replay import board_ladder
            ladder_resp = board_ladder(date=trade_date)
            ladder = {"tier_stats": ladder_resp.get("tier_stats", {})}
        except Exception:
            logger.warning("打板Agent: 梯队数据获取失败，使用空数据")

        try:
            from packages.features.longhu import build_top_traders
            raw_stocks = _kpl.get_longhu_stocks(trade_date)
            top_traders_data = build_top_traders(raw_stocks) if raw_stocks else []
        except Exception:
            logger.warning("打板Agent: 龙虎榜数据获取失败，使用空数据")

        try:
            from packages.features.backtest import run_board_backtest
            bt = run_board_backtest(sub_strategy="首板", mode="sample", years=1)
            backtest_data = bt if isinstance(bt, dict) else None
        except Exception:
            logger.warning("打板Agent: 回测数据获取失败，跳过")

        advice = _board_trading_agent.generate_advice(
            user_style=user_style,
            board_replay=board_replay,
            ladder=ladder,
            top_traders=top_traders_data,
            backtest=backtest_data,
        )

        return wrap_contract(
            {"advice": advice, "style": inp.style, "risk_preference": inp.risk_preference},
            source=data_source,
            status="real",
            trade_date=trade_date,
        )
    except Exception:
        logger.exception("打板Agent生成建议失败")
        try:
            advice = _board_trading_agent.generate_advice(
                user_style=user_style,
                board_replay={},
                ladder={},
                top_traders=[],
            )
            return wrap_contract(
                {"advice": advice, "style": inp.style, "risk_preference": inp.risk_preference},
                source="llm_mock",
                status="fallback",
                message="数据源不可用，基于模板生成建议",
            )
        except Exception:
            return wrap_contract(
                {"advice": "", "style": inp.style, "risk_preference": inp.risk_preference},
                source="kpl+llm",
                status="unavailable",
                message="数据源和LLM均不可用",
            )


class EtfRotationInput(BaseModel):
    style: str = "均衡"
    investment_horizon: str = "中期"
    risk_preference: str = "中等"


@router.post("/agent/etf-rotation")
def agent_etf_rotation(inp: EtfRotationInput):
    user_style = (f"风格: {inp.style}\n投资期限: {inp.investment_horizon}"
                  f"\n风险偏好: {inp.risk_preference}")
    try:
        data_source = "sample_engine+llm"
        signals_data: list[dict] = []
        backtest_data = None

        try:
            from packages.features.etf import build_rotation_signals
            result = build_rotation_signals(mode="sample")
            signals_data = result.get("signals", []) if isinstance(result, dict) else []
        except Exception:
            logger.warning("ETF Agent: 轮动信号获取失败，使用空数据")

        try:
            from packages.features.backtest import run_etf_backtest
            bt = run_etf_backtest(mode="sample", years=1)
            backtest_data = bt if isinstance(bt, dict) else None
        except Exception:
            logger.warning("ETF Agent: 回测数据获取失败，跳过")

        advice = _etf_rotation_agent.generate_advice(
            user_style=user_style,
            signals=signals_data,
            backtest=backtest_data,
        )

        return wrap_contract(
            {"advice": advice, "style": inp.style, "investment_horizon": inp.investment_horizon,
             "risk_preference": inp.risk_preference},
            source=data_source,
            status="real",
        )
    except Exception:
        logger.exception("ETF Agent生成建议失败")
        try:
            advice = _etf_rotation_agent.generate_advice(
                user_style=user_style,
                signals=[],
            )
            return wrap_contract(
                {"advice": advice, "style": inp.style, "investment_horizon": inp.investment_horizon,
                 "risk_preference": inp.risk_preference},
                source="llm_mock",
                status="fallback",
                message="数据源不可用，基于模板生成建议",
            )
        except Exception:
            return wrap_contract(
                {"advice": "", "style": inp.style, "investment_horizon": inp.investment_horizon,
                 "risk_preference": inp.risk_preference},
                source="sample_engine+llm",
                status="unavailable",
                message="数据源和LLM均不可用",
            )
