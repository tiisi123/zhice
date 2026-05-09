from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional
import re

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

_LLM_UNAVAILABLE_MARKERS = (
    "AI 模型暂时不可用",
    "已停止返回演示模板",
)


def _llm_unavailable(text: str) -> bool:
    return any(marker in text for marker in _LLM_UNAVAILABLE_MARKERS)


def _llm_contract_status(text: str) -> tuple[str, str]:
    if _llm_unavailable(text):
        return "unavailable", "AI 模型暂时不可用，请检查产品侧 AI 网关状态。"
    return "real", ""


def _headline_cache_key(trade_date: str, summary: dict) -> str:
    return "|".join([
        trade_date,
        str(summary.get("limit_up_count", 0)),
        str(summary.get("broken_count", 0)),
        str(summary.get("max_board", 0)),
        str(summary.get("sentiment_level", "")),
    ])


def _pick_headline_theme(sectors: list[dict], limit_up: list[dict]) -> str:
    if limit_up:
        counts: dict[str, int] = {}
        for stock in limit_up:
            names = []
            if stock.get("first_plate_name"):
                names.append(str(stock.get("first_plate_name")))
            related = stock.get("related_plates") or []
            if isinstance(related, list):
                names.extend(str(item) for item in related if item)
            for name in names:
                counts[name] = counts.get(name, 0) + 1
        if counts:
            return sorted(counts.items(), key=lambda item: item[1], reverse=True)[0][0]
    if sectors:
        top = sectors[0]
        return str(top.get("name") or top.get("PlateName") or top.get("concept_name") or "")
    return ""


def _build_deterministic_headline(summary: dict, sectors: list[dict], limit_up: list[dict]) -> str:
    sent = summary.get("sentiment_level", "中性")
    limit_up_count = int(summary.get("limit_up_count") or 0)
    broken_count = int(summary.get("broken_count") or 0)
    max_board = int(summary.get("max_board") or 0)
    theme = _pick_headline_theme(sectors, limit_up)
    theme_text = f"，主线观察 {theme}" if theme else ""
    return (
        f"{sent}，涨停{limit_up_count}家、炸板{broken_count}家、最高{max_board}板{theme_text}；"
        "以当前 KPL 涨停池/炸板池统计为准。"
    )


@router.get("/headline")
def headline(date: Optional[str] = Query(None)):
    """AI 一句话速报（无需 quota，内存缓存按日去重）。"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        kpl_stats = _kpl.get_market_statistics(trade_date)
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        sectors = _kpl.get_concept_selected(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date
        cache_key = _headline_cache_key(trade_date, summary)
        cached = _headline_cache.get_or_none(cache_key)
        if cached is not None:
            return wrap_contract(
                cached,
                source="kpl",
                status="real",
                trade_date=trade_date,
                headline=cached,
                summary=summary,
            )

        text = _build_deterministic_headline(summary, sectors, limit_up)
        _headline_cache.put(cache_key, text)
        return wrap_contract(
            text,
            source="kpl",
            status="real",
            message="AI 速报关键数字由 KPL 市场概览统一生成，避免与页面指标不一致。",
            trade_date=trade_date,
            headline=text,
            summary=summary,
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
            text = _build_deterministic_headline(s, sectors, limit_up)
            return wrap_contract(
                text,
                source="kpl",
                status="fallback",
                message="速报已降级为 KPL 规则生成",
                trade_date=trade_date,
                headline=text,
                summary=s,
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
        status, message = _llm_contract_status(report)
        # 自动归档
        try:
            if status == "real":
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
            status=status,
            message=message,
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
        from apps.api.routes.stock import stock_detail

        detail = stock_detail(code, date=trade_date)
        detail_data = detail.get("data") if isinstance(detail, dict) else None
        if detail_data and detail_data.get("found"):
            history = detail_data.get("history") or {}
            latest = (history.get("daily") or [{}])[-1] if history.get("daily") else {}
            short_pool = ((detail_data.get("intraday") or {}).get("short_pool") or {})
            themes = detail_data.get("themes", {}).get("related_plates", [])
            prompt_stock = {
                "stock_code": code,
                "stock_name": detail_data.get("name", code),
                "change_rate": detail_data.get("change_rate", 0),
                "board_count": detail_data.get("board_count", 0),
                "time": detail_data.get("time"),
                "reason": detail_data.get("combined_reason") or detail_data.get("reason") or short_pool.get("message") or "该票未进入盘中短线池，重点参考历史行情与基本面。",
                "price": latest.get("close"),
                "turnover_ratio": (detail_data.get("capital_flow") or {}).get("turnover_ratio") or (history.get("daily_basic") or {}).get("turnover_rate"),
                "data_sources": detail_data.get("data_sources", []),
            }
            report = _stock_agent.generate_summary(prompt_stock, themes)
            return wrap_contract(
                {"code": code, "name": detail_data.get("name", code), "report": report},
                source="tushare+kpl+llm",
                status="real",
                code=code,
                name=detail_data.get("name", code),
                report=report,
            )

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
        if not sectors and limit_up:
            from apps.api.routes.replay import _build_sectors_from_limit_up

            sectors = _build_sectors_from_limit_up(limit_up)
            sources.append("KPL limit_up derived sectors")
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = trade_date

        from apps.ai.context_builders.market_context import build_market_context

        context = build_market_context(summary, limit_up, broken, sectors)
        return context, sources
    except Exception:
        logger.warning("AI chat market context unavailable", exc_info=True)
        return f"## 市场数据\n- trade_date: {trade_date}\n- KPL 核心市场上下文暂不可用，回答需明确提示数据缺口。", sources


def _previous_weekday(date_str: str, steps: int = 1) -> str:
    cursor = datetime.strptime(date_str, "%Y-%m-%d").date()
    remaining = max(steps, 0)
    while remaining > 0:
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor.strftime("%Y-%m-%d")


def _resolve_chat_trade_date(
    message: str,
    history: list[dict],
    fallback_date: str,
) -> tuple[str, str]:
    """Resolve the data date from the user's question before building evidence."""
    text = message or ""

    explicit = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if explicit:
        y, m, d = explicit.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}", "explicit_date"

    compact = re.search(r"\b(20\d{6})\b", text)
    if compact:
        raw = compact.group(1)
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}", "explicit_date"

    if any(token in text for token in ("昨日", "昨天", "上个交易日", "前一交易日")):
        return _previous_weekday(fallback_date, 1), "relative_yesterday"
    if any(token in text for token in ("前日", "前天")):
        return _previous_weekday(fallback_date, 2), "relative_before_yesterday"
    if any(token in text for token in ("今日", "今天", "当日", "现在", "当前")):
        return fallback_date, "relative_today"

    # Short follow-ups like "那昨天呢" usually carry only the new temporal
    # intent. If absent, keep the page date instead of reusing a prior answer's
    # date, because the fresh question should decide the evidence window.
    for msg in reversed(history[-6:]):
        content = str(msg.get("content") or "")
        explicit = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", content)
        if explicit and any(token in text for token in ("那", "这个", "它", "呢")):
            y, m, d = explicit.groups()
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}", "history_reference"

    return fallback_date, "page_date"


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
        requested_trade_date = inp.trade_date or datetime.now().strftime("%Y-%m-%d")
        trade_date, date_resolution = _resolve_chat_trade_date(
            inp.message,
            inp.history,
            requested_trade_date,
        )
        page_ctx = _page_context(inp.current_page)
        market_context, context_sources = _build_chat_market_context(trade_date)
        evidence = build_copilot_evidence(inp.message, inp.current_page, trade_date)
        evidence["requested_trade_date"] = requested_trade_date
        evidence["date_resolution"] = date_resolution
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
题材工坊补充 API：GET /api/theme/library、GET /api/theme/library/{{theme_id}}、GET /api/theme/library/{{theme_id}}/matched。
子页面数据规则：你不能直接读取前端隐藏组件的本地状态；但只要对应后端 API 已知，就可以基于这些 API 的全局/页面上下文回答跨板块问题。
连续追问规则：结合最近 6 轮历史回答，不要丢失用户上一轮限定条件。
页面传入日期：{requested_trade_date}。
本轮问题解析后的数据时间：{trade_date}（解析规则：{date_resolution}）。如果用户说“昨日/昨天/上个交易日”，必须用解析后的历史交易日数据回答，不能沿用当前页快照。
回答约束：
- 如果用户追问“某题材的 N 只票”，必须先使用下方 evidence.theme_stocks 里的股票明细逐只分析。
- 如果用户问“主线/题材库/今日题材/昨日题材”，必须优先使用 evidence.theme_library.top 与 selected/detail；如果该证据包有 message，要把数据来源或缺口说清楚。
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
        status, message = _llm_contract_status(response)
        return {
            "message": inp.message,
            "response": response,
            "context_sources": context_sources,
            "evidence": evidence,
            "trade_date": trade_date,
            "requested_trade_date": requested_trade_date,
            "date_resolution": date_resolution,
            "data_status": status,
            "status_message": message,
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


_ETF_AGENT_MODE_TO_D004: dict[str, tuple[str, bool]] = {
    "live": ("real", False),
    "cache": ("real", False),
    "hybrid": ("fallback", False),
    "sample": ("mock", True),
    "unavailable": ("unavailable", False),
}


def _etf_agent_evidence_meta(payload: dict[str, Any] | None, *, count_key: str) -> dict[str, Any]:
    if not payload:
        return {
            "data_mode": "unavailable",
            "data_source": "unknown",
            "data_status": "unavailable",
            "mock": False,
            count_key: 0,
        }

    mode = str(payload.get("data_mode") or "sample")
    status, mock_flag = _ETF_AGENT_MODE_TO_D004.get(mode, ("fallback", False))
    meta = {
        "data_mode": mode,
        "data_source": str(payload.get("data_source") or "unknown"),
        "data_status": status,
        "mock": mock_flag,
        count_key: len(payload.get(count_key, []) or []),
    }
    if payload.get("as_of"):
        meta["as_of"] = payload.get("as_of")
    return meta


def _aggregate_etf_agent_evidence(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    modes = [str(item.get("data_mode") or "unavailable") for item in evidence.values()]
    sources = [
        str(item.get("data_source"))
        for item in evidence.values()
        if item.get("data_source") and item.get("data_source") != "unknown"
    ]
    source = "+".join(dict.fromkeys([*sources, "llm"])) or "llm"

    if modes and all(mode in {"live", "cache"} for mode in modes):
        return {"data_status": "real", "mock": False, "data_mode": "live", "source": source, "message": ""}
    if modes and all(mode == "sample" for mode in modes):
        return {
            "data_status": "mock",
            "mock": _ETF_AGENT_MODE_TO_D004["sample"][1],
            "data_mode": "sample",
            "source": source,
            "message": "ETF轮动信号和回测均为演示数据，AI建议仅供流程验证，不代表真实市场结论。",
        }
    if modes and all(mode == "unavailable" for mode in modes):
        return {
            "data_status": "unavailable",
            "mock": False,
            "data_mode": "unavailable",
            "source": source,
            "message": "ETF轮动信号和回测数据均不可用，无法形成可靠建议。",
        }
    return {
        "data_status": "fallback",
        "mock": False,
        "data_mode": "hybrid",
        "source": source,
        "message": "ETF轮动证据包含降级或样例数据，已在 evidence 中标明来源。",
    }


@router.post("/agent/etf-rotation")
def agent_etf_rotation(inp: EtfRotationInput):
    user_style = (f"风格: {inp.style}\n投资期限: {inp.investment_horizon}"
                  f"\n风险偏好: {inp.risk_preference}")
    try:
        signals_result: dict[str, Any] | None = None
        signals_data: list[dict] = []
        backtest_data: dict[str, Any] | None = None

        try:
            from packages.features.etf import build_rotation_signals
            result = build_rotation_signals(mode="auto")
            signals_result = result if isinstance(result, dict) else None
            signals_data = signals_result.get("signals", []) if signals_result else []
        except Exception:
            logger.warning("ETF Agent: 轮动信号获取失败，使用空数据")

        try:
            from packages.features.backtest import run_etf_backtest
            bt = run_etf_backtest(mode="auto", years=1)
            backtest_data = bt if isinstance(bt, dict) else None
        except Exception:
            logger.warning("ETF Agent: 回测数据获取失败，跳过")

        evidence = {
            "signals": _etf_agent_evidence_meta(signals_result, count_key="signals"),
            "backtest": _etf_agent_evidence_meta(backtest_data, count_key="equity_curve"),
        }
        aggregate = _aggregate_etf_agent_evidence(evidence)
        advice = _etf_rotation_agent.generate_advice(
            user_style=user_style,
            signals=signals_data,
            backtest=backtest_data,
        )

        data = {
            "advice": advice,
            "style": inp.style,
            "investment_horizon": inp.investment_horizon,
            "risk_preference": inp.risk_preference,
            "evidence": evidence,
        }
        return wrap_contract(
            data,
            source=aggregate["source"],
            status=aggregate["data_status"],
            mock=aggregate["mock"],
            message=aggregate["message"],
            data_source=aggregate["source"],
            data_mode=aggregate["data_mode"],
            as_of=evidence["signals"].get("as_of"),
            fallback_reason=aggregate["message"] or None,
            evidence=evidence,
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
