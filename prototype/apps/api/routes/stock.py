from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_kpl
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

@router.get("/{code}")
def stock_detail(code: str, date: Optional[str] = Query(None)):
    """个股详情：聚合 KPL 涨停/炸板/热股数据 + KPL 题材数据"""
    try:
        # 从涨停池查找
        limit_up = _kpl.get_limit_up(date)
        broken = _kpl.get_broken(date)
        hot_stocks = _kpl.get_hot_stocks(date)

        stock_info = None
        match_source = None

        # 在涨停池中查找
        for s in limit_up:
            if s.get("stock_code", "")[:6] == code[:6]:
                stock_info = s
                match_source = "limit_up"
                break

        # 在炸板池中查找
        if not stock_info:
            for s in broken:
                if s.get("stock_code", "")[:6] == code[:6]:
                    stock_info = s
                    match_source = "broken"
                    break

        # 在热股中查找
        if not stock_info:
            for s in hot_stocks:
                if s.get("stock_code", "")[:6] == code[:6]:
                    stock_info = s
                    match_source = "hot"
                    break

        if not stock_info:
            return wrap_contract(
                {},
                source="kpl",
                status="empty",
                mock=False,
                message="该股票今日不在涨停/炸板/热股池中",
                code=code,
                found=False,
                themes=[],
                capital_flow=None,
            )

        # 获取关联题材
        related_plates = stock_info.get("related_plates", [])
        first_plate = stock_info.get("first_plate_name", "") or stock_info.get("plate_name", "")

        # 构建资金流向近似（用换手率+流通市值估算）
        turnover = stock_info.get("turnover_ratio", 0)
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
        change_rate = stock_info.get("change_rate", 0)

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
            "name": stock_info.get("stock_name", ""),
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
            "kline_label": f"{'连板' + str(board_count) if board_count > 1 else '首板' if match_source == 'limit_up' else '炸板' if match_source == 'broken' else '热股'}",
            "match_source": match_source,
        }
        return wrap_contract(
            payload,
            source="kpl",
            status="real",
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
