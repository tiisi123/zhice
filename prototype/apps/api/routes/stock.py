from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_kpl, get_tushare
from packages.connectors.kpl.sentinel import cookie_unavailable_message, from_client_state
from packages.features.pattern_match import (
    aggregate_outlook,
    match_patterns,
)

router = APIRouter()

_kpl = get_kpl()


def _to_ts_code(code: str) -> str:
    raw = code[:6]
    if raw.startswith(("6", "9")):
        return f"{raw}.SH"
    return f"{raw}.SZ"


def _find_stock_in_pool(code: str, pools: list[tuple[str, list[dict]]]) -> tuple[dict | None, str | None]:
    needle = code[:6]
    for source, pool in pools:
        for stock in pool or []:
            if str(stock.get("stock_code", ""))[:6] == needle:
                return stock, source
    return None, None


def _fetch_tushare_profile(code: str) -> tuple[dict, dict, list[dict], bool]:
    ts = get_tushare()
    if not ts.configured:
        return {}, {}, [], False
    basic = ts.get_stock_basic(code) or {}
    daily_basic = ts.get_daily_basic_latest(code) or {}
    daily = ts.get_daily(_to_ts_code(code), limit=60) or []
    return basic, daily_basic, daily, True

@router.get("/{code}")
def stock_detail(code: str, date: Optional[str] = Query(None)):
    """个股详情：任意 A 股均可分析。

    数据口径：
    - 历史行情 / 基本资料 / 估值指标：Tushare
    - 盘中短线状态 / 涨停池 / 炸板池 / 热股池：KPL
    """
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        basic, daily_basic, daily_rows, tushare_configured = _fetch_tushare_profile(code)

        # 从涨停池查找
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        hot_stocks = _kpl.get_hot_stocks(trade_date)
        stock_info, match_source = _find_stock_in_pool(
            code,
            [("limit_up", limit_up), ("broken", broken), ("hot", hot_stocks)],
        )
        stock_info = stock_info or {}
        realtime_quote = _kpl.get_stock_realtime(code) or {}
        realtime_sentinel = from_client_state(_kpl)
        realtime_status = (
            "real"
            if realtime_quote
            else "unavailable"
            if realtime_sentinel
            else "empty"
        )
        realtime_message = (
            ""
            if realtime_quote
            else cookie_unavailable_message(realtime_sentinel)
            if realtime_sentinel
            else "KPL 全市场实时排行未返回该票；仍可使用 Tushare 历史行情/基本面分析。"
        )
        realtime_source = realtime_quote.get("source") or "kpl_new_stock_ranking"

        # 获取关联题材
        related_plates = stock_info.get("related_plates", [])
        first_plate = stock_info.get("first_plate_name", "") or stock_info.get("plate_name", "")

        # 构建资金流向近似（用换手率+流通市值估算）
        turnover = stock_info.get("turnover_ratio") or realtime_quote.get("turnover_ratio") or 0
        non_restricted = stock_info.get("non_restricted_capital", 0)
        total_capital = stock_info.get("total_capital", 0)

        capital_flow = {
            "turnover_ratio": turnover,
            "non_restricted_capital": non_restricted,
            "total_capital": total_capital,
            "estimated_net_inflow": round(non_restricted * turnover / 100 * 0.3, 0) if non_restricted else None,
        }

        # 涨停/炸板原因分析
        reason = stock_info.get("reason", "")
        combined_reason = stock_info.get("combined_reason", reason)
        board_count = stock_info.get("board_count", 0)
        latest_daily = daily_rows[-1] if daily_rows else {}
        change_rate = stock_info.get("change_rate", realtime_quote.get("change_rate", latest_daily.get("pct_chg", 0)))
        name = stock_info.get("stock_name") or realtime_quote.get("stock_name") or basic.get("name") or code[:6]

        # 同题材联动股
        linked_stocks = []
        if first_plate:
            for s in limit_up:
                if s.get("first_plate_name", "") == first_plate and s.get("stock_code") != code[:6]:
                    linked_stocks.append({
                        "code": s.get("stock_code", ""),
                        "name": s.get("stock_name", ""),
                        "change_rate": s.get("change_rate", 0),
                        "board_count": s.get("board_count", 0),
                    })
                    if len(linked_stocks) >= 5:
                        break

        payload = {
            "code": code,
            "found": True,
            "name": name,
            "change_rate": change_rate,
            "board_count": board_count,
            "time": stock_info.get("time"),
            "reason": reason,
            "combined_reason": combined_reason,
            "themes": {
                "main_theme": first_plate,
                "related_plates": related_plates,
                "hot_score": min(100, len(related_plates) * 15 + board_count * 20 + (30 if match_source == "limit_up" else 0)),
            },
            "capital_flow": capital_flow,
            "linked_stocks": linked_stocks,
            "kline_label": f"{'连板' + str(board_count) if board_count > 1 else '首板' if match_source == 'limit_up' else '炸板' if match_source == 'broken' else '热股' if match_source == 'hot' else '普通标的'}",
            "match_source": match_source,
            "intraday": {
                "source": realtime_source,
                "trade_date": trade_date,
                "status": realtime_status,
                "message": realtime_message,
                "realtime": realtime_quote,
                "short_pool": {
                    "in_pool": bool(match_source),
                    "pool": match_source,
                    "message": "该票当前盘中短线事件为空；不在涨停/炸板/热股池。" if not match_source else "",
                },
            },
            "history": {
                "source": "tushare",
                "configured": tushare_configured,
                "stock_basic": basic,
                "daily_basic": daily_basic,
                "daily": daily_rows,
                "message": "" if tushare_configured else "TUSHARE_TOKEN 未配置，历史行情/基本面不可用。",
            },
            "data_sources": [
                {"name": "历史行情/基本资料/估值", "source": "tushare", "status": "real" if daily_rows or basic or daily_basic else "empty" if tushare_configured else "unavailable"},
                {"name": "盘中全市场实时行情", "source": realtime_source, "status": realtime_status},
                {"name": "盘中涨停/炸板/热股事件", "source": "kpl_event_pools", "status": "real" if match_source else "empty"},
            ],
        }
        return wrap_contract(
            payload,
            source="tushare+kpl",
            status="real" if (tushare_configured or match_source) else "unavailable",
            mock=False,
            **payload,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取个股详情失败: {str(e)}")


@router.get("/{code}/themes")
def stock_themes(code: str, date: Optional[str] = Query(None)):
    """个股题材归属：从 KPL 概念板块中查找该股所属板块"""
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        sectors = _kpl.get_concept_selected(trade_date)
        matched = []
        for sector in sectors:
            plate_id = sector.get("PlateID", sector.get("plate_id", ""))
            plate_name = sector.get("PlateName", sector.get("plate_name", ""))
            change = sector.get("ChangePercent", sector.get("change_percent", 0))
            if not plate_id:
                continue
            # 查询板块内个股，检查是否包含目标股票
            try:
                detail = _kpl.get_concept_detail(plate_id, trade_date)
                for stock in detail:
                    stock_code = stock.get("SecurityCode", stock.get("stock_code", ""))
                    if stock_code[:6] == code[:6]:
                        matched.append({
                            "plate_id": plate_id,
                            "plate_name": plate_name,
                            "change_percent": change,
                        })
                        break
            except Exception:
                continue
            if len(matched) >= 10:
                break

        return wrap_contract(
            matched,
            source="kpl",
            status="real" if matched else "empty",
            code=code,
            themes=matched,
            count=len(matched),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取个股题材失败: {str(e)}")


@router.get("/{code}/pattern-match")
def stock_pattern_match(code: str, top_k: int = Query(5, ge=1, le=10)):
    """
    PRD M4A-06：K 线形态匹配。
    返回与该股近 30 日走势最相似的历史牛股形态 Top-K + 后续涨幅统计。
    """
    try:
        from packages.connectors.registry import get_tushare

        ts = get_tushare()
        if not ts.configured:
            return wrap_contract(
                [],
                source="tushare_daily",
                status="unavailable",
                mock=False,
                message="TUSHARE_TOKEN 未配置，无法获取真实历史 K 线",
                code=code,
                query_seq=[],
                matches=[],
                outlook={},
                disclaimer="形态匹配仅供参考，过往走势不代表未来收益。",
            )
        rows = ts.get_daily(_to_ts_code(code), limit=30)
        closes = [float(r.get("close") or 0) for r in rows if float(r.get("close") or 0) > 0]
        if len(closes) < 20:
            return wrap_contract(
                [],
                source="tushare_daily",
                status="empty",
                mock=False,
                message="真实历史 K 线不足，无法进行形态匹配",
                code=code,
                query_seq=[],
                matches=[],
                outlook={},
                disclaimer="形态匹配仅供参考，过往走势不代表未来收益。",
            )

        base = closes[0]
        query_seq = [((v / base) - 1) * 100 for v in closes]
        matches = match_patterns(query_seq, top_k=top_k)
        outlook = aggregate_outlook(matches)

        return wrap_contract(
            matches,
            source="tushare_daily",
            status="real",
            mock=False,
            code=code,
            query_seq=[round(v, 2) for v in query_seq],
            matches=matches,
            outlook=outlook,
            disclaimer="形态匹配仅供参考，过往走势不代表未来收益。",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"K线形态匹配失败: {str(e)}")
