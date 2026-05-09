from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from packages.connectors.registry import get_kpl
from packages.features.market import build_market_summary

_kpl = get_kpl()


THEME_HINTS = (
    "AI硬件", "算力", "商业航天", "机器人", "低空经济", "半导体", "芯片",
    "新能源车", "固态电池", "光伏", "医药", "消费", "军工", "证券",
)


def _stock_name(stock: dict) -> str:
    return str(stock.get("stock_name") or stock.get("name") or stock.get("Name") or "")


def _stock_code(stock: dict) -> str:
    return str(stock.get("stock_code") or stock.get("code") or stock.get("Code") or "")


def _plates(stock: dict) -> list[str]:
    raw = stock.get("related_plates") or stock.get("sectors") or []
    if isinstance(raw, str):
        plates = re.split(r"[,，、\s]+", raw)
    elif isinstance(raw, list):
        plates = [str(x) for x in raw]
    else:
        plates = []
    first = stock.get("first_plate_name") or stock.get("PlateName") or stock.get("concept_name")
    if first:
        plates.append(str(first))
    return [p for p in dict.fromkeys(plates) if p]


def _matches_theme(stock: dict, theme: str) -> bool:
    blob = " ".join([
        _stock_name(stock),
        str(stock.get("reason") or ""),
        str(stock.get("涨停原因") or ""),
        " ".join(_plates(stock)),
    ])
    return theme.lower() in blob.lower()


def _extract_theme(message: str, sectors: list[dict]) -> str | None:
    for hint in THEME_HINTS:
        if hint in message:
            return hint
    names: list[str] = []
    for sec in sectors[:30]:
        name = (
            sec.get("PlateName")
            or sec.get("concept_name")
            or sec.get("name")
            or sec.get("col2")
        )
        if name:
            names.append(str(name))
    names.sort(key=len, reverse=True)
    for name in names:
        if name and name in message:
            return name
    m = re.search(r"([\u4e00-\u9fa5A-Za-z0-9/+-]{2,20})(?:这|板块|题材|涨停|这\s*\d+\s*只)", message)
    return m.group(1) if m else None


def _compact_stock(stock: dict) -> dict[str, Any]:
    return {
        "stock_code": _stock_code(stock),
        "stock_name": _stock_name(stock),
        "board_count": stock.get("board_count") or stock.get("连板数") or 1,
        "change_rate": stock.get("change_rate") or stock.get("涨跌幅"),
        "reason": stock.get("reason") or stock.get("涨停原因") or "",
        "seal_amount": stock.get("seal_amount") or stock.get("封单金额") or 0,
        "turnover_ratio": stock.get("turnover_ratio") or stock.get("换手率") or 0,
        "related_plates": _plates(stock)[:8],
        "is_leader": bool(stock.get("is_leader")),
    }


def build_theme_stocks(theme: str, trade_date: str) -> dict[str, Any]:
    limit_up = _kpl.get_limit_up(trade_date)
    broken = _kpl.get_broken(trade_date)
    matched_limit = [_compact_stock(s) for s in limit_up if _matches_theme(s, theme)]
    matched_broken = [_compact_stock(s) for s in broken if _matches_theme(s, theme)]
    matched_limit.sort(key=lambda s: int(s.get("board_count") or 1), reverse=True)
    return {
        "theme": theme,
        "trade_date": trade_date,
        "limit_up_count": len(matched_limit),
        "broken_count": len(matched_broken),
        "limit_up_stocks": matched_limit[:20],
        "broken_stocks": matched_broken[:10],
    }


def build_theme_library_context(theme: str | None, trade_date: str) -> dict[str, Any]:
    """Build KPL theme-library evidence from the product API contract.

    The theme route owns cache/fallback/matching policy, so Copilot consumes it
    instead of reconstructing another source order here.
    """
    from apps.api.routes import theme as theme_route

    library_resp = theme_route.theme_library(date=trade_date)
    rows = library_resp.get("data") if isinstance(library_resp, dict) else []
    rows = rows if isinstance(rows, list) else []
    selected = None
    if theme:
        norm = theme_route._normalize_name(theme)
        for row in rows:
            row_name = row.get("theme_name") or ""
            row_norm = theme_route._normalize_name(str(row_name))
            if norm and row_norm and (norm == row_norm or norm in row_norm or row_norm in norm):
                selected = row
                break
    if selected is None and rows:
        selected = rows[0]

    detail = None
    if selected and selected.get("theme_id"):
        detail_resp = theme_route.theme_library_detail(str(selected.get("theme_id")), date=trade_date)
        detail = detail_resp.get("data") if isinstance(detail_resp, dict) else None

    top_rows = [
        {
            "theme_id": row.get("theme_id"),
            "theme_name": row.get("theme_name"),
            "theme_hot_num": row.get("theme_hot_num"),
            "theme_zt_num": row.get("theme_zt_num"),
            "market_match": row.get("market_match"),
        }
        for row in rows[:10]
    ]
    return {
        "status": library_resp.get("data_status") if isinstance(library_resp, dict) else "unavailable",
        "source": library_resp.get("source") if isinstance(library_resp, dict) else "kpl_theme_library",
        "message": library_resp.get("message") if isinstance(library_resp, dict) else "",
        "top": top_rows,
        "selected": selected,
        "detail": detail,
    }


def build_copilot_evidence(message: str, current_page: str | None, trade_date: str | None) -> dict[str, Any]:
    date = trade_date or datetime.now().strftime("%Y-%m-%d")
    sources = [
        "KPL market_statistics",
        "KPL limit_up",
        "KPL broken",
        "KPL concept_selected",
    ]
    evidence: dict[str, Any] = {
        "trade_date": date,
        "current_page": current_page or "",
        "sources": sources,
        "market": {},
        "sectors": [],
        "theme_stocks": None,
        "warnings": [],
    }

    try:
        kpl_stats = _kpl.get_market_statistics(date)
        limit_up = _kpl.get_limit_up(date)
        broken = _kpl.get_broken(date)
        sectors = _kpl.get_concept_selected(date)
        if not sectors and limit_up:
            from apps.api.routes.replay import _build_sectors_from_limit_up

            sectors = _build_sectors_from_limit_up(limit_up)
            evidence["sources"].append("KPL limit_up derived sectors")
        summary = build_market_summary(kpl_stats, limit_up, broken)
        summary["trade_date"] = date

        evidence["market"] = {
            "limit_up_count": summary.get("limit_up_count", 0),
            "broken_count": summary.get("broken_count", 0),
            "broken_rate": summary.get("broken_rate", 0),
            "max_board": summary.get("max_board", 0),
            "sentiment_level": summary.get("sentiment_level", ""),
        }
        evidence["sectors"] = [
            {
                "name": s.get("PlateName") or s.get("concept_name") or s.get("name") or s.get("col2"),
                "change": s.get("ChangePercent") or s.get("concept_increase") or s.get("col4"),
                "intensity": s.get("Intensity") or s.get("concept_intensity") or s.get("col3"),
                "main_force": s.get("MainForce") or s.get("concept_net_amount") or s.get("col7"),
            }
            for s in sectors[:15]
        ]

        theme = _extract_theme(message, sectors)
        if any(token in message for token in ("题材", "主线", "概念", "板块", "热点")):
            evidence["theme_library"] = build_theme_library_context(theme, date)
            evidence["sources"].append("GET /api/theme/library")
            if theme:
                evidence["sources"].append(f"GET /api/theme/library matched: {theme}")
        if theme and any(token in message for token in ("票", "股", "涨停", "分析", "建议", "题材", "板块")):
            evidence["theme_stocks"] = build_theme_stocks(theme, date)
            evidence["sources"].append(f"KPL theme stock match: {theme}")
    except Exception as exc:
        evidence["warnings"].append(f"KPL context unavailable: {exc}")

    return evidence


def format_copilot_evidence(evidence: dict[str, Any]) -> str:
    compact = {
        "trade_date": evidence.get("trade_date"),
        "current_page": evidence.get("current_page"),
        "market": evidence.get("market"),
        "sectors": evidence.get("sectors", [])[:10],
        "theme_library": evidence.get("theme_library"),
        "theme_stocks": evidence.get("theme_stocks"),
        "warnings": evidence.get("warnings", []),
    }
    return json.dumps(compact, ensure_ascii=False, indent=2)
