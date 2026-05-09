from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

from apps.api.utils.contract import wrap_contract
from packages.connectors.kpl.sentinel import (
    cookie_unavailable_message,
    from_client_state,
    is_cookie_missing,
    is_upstream_error,
)
from packages.connectors.registry import get_kpl

router = APIRouter()

_kpl = get_kpl()

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
_THEME_LIBRARY_CACHE = _CACHE_DIR / "kpl_theme_library.json"


def _maybe_unavailable(client, *, trade_date: str, body=None, source="kpl", **extra) -> Optional[dict]:
    """Surface KPL Cookie missing / upstream error as theme-route unavailable.

    Theme module endpoints all hit KPL realtime/history (cookie-required).
    When the operator has not configured cookie, downstream routes silently
    return empty arrays today — this helper turns that into an explicit
    ``status='unavailable'`` so the front-end DataStatusBadge surfaces the
    operator-action message instead of looking like "no themes today".
    """
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        [] if body is None else body,
        source=source,
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        **extra,
    )


def _trade_date(date: Optional[str]) -> str:
    return date or datetime.now().strftime("%Y-%m-%d")


def _to_float(value) -> float:
    try:
        if value in (None, "", "--"):
            return 0.0
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"(概念|板块|题材|产业链|梳理)$", "", text)
    return re.sub(r"[\s/_+\-·（）()]", "", text)


_THEME_ALIAS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ai硬件": ("it服务", "消费电子", "通信设备", "元件", "算力", "半导体"),
    "国产芯片": ("半导体", "元件", "芯片", "集成电路", "军工电子"),
    "商业航天": ("军工电子", "通信设备", "专用设备", "航天"),
    "人形机器人": ("通用设备", "专用设备", "自动化", "机器人"),
    "算力": ("it服务", "通信设备", "云计算", "液冷", "服务器"),
    "电力": ("电力", "燃气", "电网", "电源"),
    "固态电池": ("电池", "锂电", "化学制品"),
}


def _alias_keywords(theme_name: str) -> tuple[str, ...]:
    norm = _normalize_name(theme_name)
    for key, aliases in _THEME_ALIAS_KEYWORDS.items():
        if key in norm or norm in key:
            return aliases
    return ()


def _theme_name(row: dict) -> str:
    return str(
        row.get("theme_name")
        or row.get("Name")
        or row.get("ThemeName")
        or row.get("PlateName")
        or row.get("concept_name")
        or ""
    ).strip()


def _sector_name(row: dict) -> str:
    return str(
        row.get("PlateName")
        or row.get("plate_name")
        or row.get("concept_name")
        or row.get("first_plate_name")
        or row.get("name")
        or ""
    ).strip()


def _read_theme_library_cache() -> tuple[list[dict], str]:
    if not _THEME_LIBRARY_CACHE.exists():
        return [], ""
    try:
        payload = json.loads(_THEME_LIBRARY_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return [], ""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)], "local_cache"
    rows = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return [], ""
    return [row for row in rows if isinstance(row, dict)], str(payload.get("source") or "local_cache")


def _build_sectors_from_kpl_pool(trade_date: str) -> list[dict]:
    limit_up = _kpl.get_limit_up(trade_date)
    if not limit_up:
        return []
    plate_map: dict[str, list[dict]] = {}
    for s in limit_up:
        for plate in s.get("related_plates", []):
            if not plate:
                continue
            plate_map.setdefault(plate, []).append(s)
    result = []
    for idx, (name, stocks) in enumerate(
        sorted(plate_map.items(), key=lambda x: len(x[1]), reverse=True)
    ):
        changes = [s["change_rate"] for s in stocks]
        avg = round(sum(changes) / len(changes), 2) if changes else 0
        result.append({
            "PlateID": f"kpl_pool_{idx}",
            "PlateName": name,
            "ChangePercent": avg,
            "LimitUpNum": len(stocks),
            "MainForce": 0,
            "_stocks": stocks,
        })
    return result


def _build_theme_list_from_sectors(trade_date: str) -> list[dict]:
    sectors = sector_list(trade_date)
    rows = sectors.get("data") if isinstance(sectors, dict) else []
    result = []
    for item in rows or []:
        name = item.get("PlateName") or item.get("concept_name") or item.get("name")
        if not name:
            continue
        result.append({
            "ID": item.get("PlateID") or item.get("id") or name,
            "Name": name,
            "ThemeName": name,
            "PlateName": name,
            "ChangePercent": item.get("ChangePercent") or item.get("change_rate") or item.get("concept_increase") or 0,
            "LimitUpNum": item.get("LimitUpNum") or item.get("limit_up_count") or 0,
            "source": sectors.get("source") or "kpl_pool_derived",
        })
    return result


def _normalize_library_row(row: dict) -> dict:
    theme_id = row.get("theme_id") or row.get("ID") or row.get("id") or row.get("PlateID") or row.get("Name") or ""
    name = row.get("theme_name") or row.get("Name") or row.get("ThemeName") or row.get("PlateName") or row.get("concept_name") or ""
    return {
        "theme_id": str(theme_id),
        "theme_name": name,
        "theme_hot_num": row.get("theme_hot_num") or row.get("HotNum") or row.get("hot_num") or row.get("Intensity") or row.get("concept_intensity") or 0,
        "theme_zt_num": row.get("theme_zt_num") or row.get("LimitUpNum") or row.get("limit_up_num") or 0,
        "theme_createtime": row.get("theme_createtime") or row.get("CreateTime") or row.get("create_time") or "",
        "change_percent": row.get("ChangePercent") or row.get("change_rate") or row.get("concept_increase") or 0,
        "members": row.get("members") or [],
        "source": row.get("source") or "kpl",
        "raw": row,
    }


def _library_rows_from_theme_list(trade_date: str) -> tuple[list[dict], str, str]:
    cached_rows, cache_source = _read_theme_library_cache()
    if cached_rows:
        rows = [_normalize_library_row(row) for row in cached_rows]
        rows.sort(
            key=lambda item: (
                _to_float(item.get("theme_hot_num")),
                _to_float(item.get("theme_zt_num")),
            ),
            reverse=True,
        )
        return rows, cache_source or "kpl_theme_library_cache", "题材库列表来自本地采集缓存；可通过采集脚本刷新。"

    rows = _kpl.get_theme_list(trade_date) or []
    unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
    if rows and unavail is None:
        return [_normalize_library_row(row) for row in rows if isinstance(row, dict)], "kpl_theme_library", ""

    derived = _build_theme_list_from_sectors(trade_date)
    if derived:
        reason = "KPL 题材库列表不可用" if unavail is not None else "KPL 题材库列表为空"
        return (
            [_normalize_library_row(row) for row in derived if isinstance(row, dict)],
            "kpl_sector_derived",
            f"{reason}，已用板块强度/涨停池派生题材库列表。",
        )
    return [], "kpl_theme_library", "KPL 题材库列表不可用或为空，且没有可派生的板块/涨停池数据。"


def _find_library_row(theme_id: str, trade_date: str) -> dict:
    rows, _, _ = _library_rows_from_theme_list(trade_date)
    target = str(theme_id)
    for row in rows:
        if str(row.get("theme_id") or "") == target:
            return row
    return {}


def _members_from_library_row(row: dict) -> list[dict]:
    members = row.get("members") or []
    if not isinstance(members, list):
        return []
    result: list[dict] = []
    for item in members:
        if not isinstance(item, dict):
            continue
        result.append({
            "stock_tag_name": item.get("stock_tag_name") or "",
            "stock_code": str(item.get("stock_code") or "")[:6],
            "stock_name": item.get("stock_name") or "",
            "stock_hot_num": item.get("stock_hot_num") or 0,
            "stock_tag_reason": item.get("stock_tag_reason") or "",
            "source": "theme_library_cache",
        })
    return result


def _build_quote_index(trade_date: str) -> dict[str, dict]:
    date_arg = "" if trade_date == datetime.now().strftime("%Y-%m-%d") else trade_date
    quotes = _kpl.get_stock_ranking(date=date_arg) or []
    return {
        str(row.get("stock_code") or row.get("code") or "")[:6]: row
        for row in quotes
        if str(row.get("stock_code") or row.get("code") or "")[:6]
    }


def _enrich_theme_members(detail: dict, trade_date: str) -> tuple[list[dict], str]:
    members = detail.get("theme_sub_detail") or []
    if not isinstance(members, list) or not members:
        return [], "empty"
    try:
        quote_index = _build_quote_index(trade_date)
    except Exception:
        quote_index = {}
    if not quote_index:
        return [
            {
                **item,
                "stock_code": str(item.get("stock_code") or item.get("StockID") or item.get("code") or "")[:6],
                "quote_status": "unavailable",
            }
            for item in members
            if isinstance(item, dict)
        ], "unavailable"
    enriched: list[dict] = []
    matched = 0
    for item in members:
        if not isinstance(item, dict):
            continue
        code = str(item.get("stock_code") or item.get("StockID") or item.get("code") or "")[:6]
        quote = quote_index.get(code) if code else None
        row = dict(item)
        row["stock_code"] = code
        row["quote_status"] = "matched" if quote else "missing"
        if quote:
            matched += 1
            row.update({
                "stock_name": row.get("stock_name") or quote.get("stock_name"),
                "price": quote.get("price"),
                "change_rate": quote.get("change_rate"),
                "turnover_ratio": quote.get("turnover_ratio"),
                "amount": quote.get("amount"),
                "net_flow": quote.get("net_flow"),
                "ranking_score": quote.get("ranking_score"),
                "quote_source": quote.get("source") or "kpl_new_stock_ranking",
            })
        enriched.append(row)
    status = "matched" if matched else "missing"
    return enriched, status


def _match_theme_to_market(theme_row: dict, trade_date: str) -> dict:
    name = _theme_name(theme_row)
    norm = _normalize_name(name)
    sectors = sector_list(date=trade_date)
    sector_rows = sectors.get("data") if isinstance(sectors, dict) else []
    matches: list[dict] = []
    aliases = tuple(_normalize_name(item) for item in _alias_keywords(name))
    for sec in sector_rows or []:
        sec_name = _sector_name(sec)
        sec_norm = _normalize_name(sec_name)
        if not norm or not sec_norm:
            continue
        score = 0
        rule = ""
        if norm == sec_norm:
            score = 100
            rule = "normalized_equal"
        elif norm in sec_norm or sec_norm in norm:
            score = 80
            rule = "normalized_contains"
        elif any(alias and (alias in sec_norm or sec_norm in alias) for alias in aliases):
            score = 55
            rule = "alias_keyword"
        if score:
            matches.append({
                "match_score": score,
                "match_rule": rule,
                "plate_id": sec.get("PlateID") or sec.get("plate_id"),
                "plate_name": sec_name,
                "change_percent": sec.get("ChangePercent") or sec.get("change_rate") or sec.get("concept_increase") or 0,
                "limit_up_num": sec.get("LimitUpNum") or sec.get("limit_up_num") or 0,
                "intensity": sec.get("Intensity") or sec.get("intensity") or sec.get("concept_intensity") or 0,
                "source": sec.get("source") or sectors.get("source") or "kpl",
            })
    matches.sort(key=lambda row: (row["match_score"], _to_float(row.get("intensity"))), reverse=True)
    return {
        "theme_name": name,
        "matched": bool(matches),
        "best_match": matches[0] if matches else None,
        "candidates": matches[:5],
        "match_status": "matched" if matches else "unmatched",
    }


def _merge_sector_lists(primary: list[dict], pool: list[dict]) -> list[dict]:
    if not primary:
        return pool
    if not pool:
        return primary
    seen_names = set()
    merged: list[dict] = []
    for item in pool + primary:
        name = (
            item.get("PlateName")
            or item.get("plate_name")
            or item.get("concept_name")
            or item.get("first_plate_name")
            or item.get("name")
            or ""
        )
        key = str(name).strip()
        if key and key in seen_names:
            continue
        if key:
            seen_names.add(key)
        merged.append(item)
    return merged


def _sector_name_for_plate(plate_id: str, trade_date: str) -> str:
    sectors = _kpl.get_concept_selected(trade_date) or []
    for sec in sectors:
        sid = str(sec.get("PlateID") or sec.get("plate_id") or sec.get("ID") or "")
        if sid != str(plate_id):
            continue
        return (
            sec.get("PlateName")
            or sec.get("plate_name")
            or sec.get("concept_name")
            or sec.get("first_plate_name")
            or sec.get("Name")
            or ""
        )
    return ""


def _derive_sector_detail_from_pool(plate_id: str, trade_date: str) -> list[dict]:
    target_name = _sector_name_for_plate(plate_id, trade_date)
    if not target_name:
        return []
    detail: list[dict] = []
    for stock in _kpl.get_limit_up(trade_date) or []:
        plates = stock.get("related_plates") or []
        if target_name not in plates:
            continue
        detail.append({
            "SecurityCode": stock.get("stock_code"),
            "SecurityName": stock.get("stock_name"),
            "ChangePercent": stock.get("change_rate", 0),
            "board_count": stock.get("board_count", 0),
            "first_plate_name": target_name,
            "source": "kpl_limit_up_pool",
        })
    return detail


@router.get("/list")
def theme_list(date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        data = _kpl.get_theme_list(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            data = _build_theme_list_from_sectors(trade_date)
            if data:
                return wrap_contract(
                    data,
                    source="kpl_sector_derived",
                    status="real",
                    message="KPL 主题列表不可用，已用板块/涨停池派生题材列表。",
                    trade_date=trade_date,
                    count=len(data),
                )
            return unavail
        if not data:
            data = _build_theme_list_from_sectors(trade_date)
            if data:
                return wrap_contract(
                    data,
                    source="kpl_sector_derived",
                    status="real",
                    message="KPL 主题列表为空，已用板块/涨停池派生题材列表。",
                    trade_date=trade_date,
                    count=len(data),
                )
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取题材列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/sectors")
def sector_list(date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        data = _kpl.get_concept_selected(trade_date)
        source = "kpl"
        pool_data = _build_sectors_from_kpl_pool(trade_date)
        if data and pool_data:
            data = _merge_sector_lists(data, pool_data)
            source = "kpl_mixed"
        elif not data:
            data = pool_data
            source = "kpl_pool_derived"
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None and not data:
            return unavail
        try:
            from packages.features.theme_novelty import mark_themes
            data = mark_themes(data, trade_date)
        except Exception:
            pass
        data = data or []
        return wrap_contract(
            data,
            source=source,
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取板块列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/library")
def theme_library(date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        rows, source, message = _library_rows_from_theme_list(trade_date)
        rows = [{"market_match": None, **row} for row in rows]
        status = "fallback" if source == "kpl_sector_derived" and rows else "real"
        if not rows and message:
            status = "unavailable"
        return wrap_contract(
            rows,
            source=source,
            status=status,
            message=message,
            trade_date=trade_date,
            count=len(rows),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl_theme_library",
            status="unavailable",
            message=f"获取题材库列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/library/{theme_id}")
def theme_library_detail(theme_id: str, date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        detail = _kpl.get_theme_library_detail(theme_id) or {}
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, body={}, total=0)
        if detail and unavail is None:
            enriched, quote_status = _enrich_theme_members(detail, trade_date)
            detail["theme_sub_detail"] = enriched
            detail["quote_match_status"] = quote_status
            detail["market_match"] = _match_theme_to_market(detail, trade_date)
            return wrap_contract(
                detail,
                source="kpl_theme_library",
                status="real",
                trade_date=trade_date,
                total=1,
            )

        row = _find_library_row(theme_id, trade_date)
        if row:
            cached_members = _members_from_library_row(row)
            fallback_detail = {
                "theme_id": row.get("theme_id"),
                "theme_name": row.get("theme_name"),
                "theme_createtime": row.get("theme_createtime"),
                "theme_sub_detail": cached_members,
                "stock_table": [],
                "brief_intro": "",
                "introduction_html": "",
                "matched_sector": row,
                "quote_match_status": "empty",
                "market_match": _match_theme_to_market(row, trade_date),
            }
            if cached_members:
                enriched, quote_status = _enrich_theme_members(fallback_detail, trade_date)
                fallback_detail["theme_sub_detail"] = enriched
                fallback_detail["quote_match_status"] = quote_status
            reason = "KPL 题材库详情不可用" if unavail is not None else "KPL 题材库详情为空"
            suffix = "已使用题材库冷启动缓存成员。" if cached_members else "已保留题材列表/板块派生信息，细分个股与正文待 KPL 详情恢复。"
            return wrap_contract(
                fallback_detail,
                source=row.get("source") or "kpl_theme_library_cache",
                status="fallback",
                message=f"{reason}，{suffix}",
                trade_date=trade_date,
                total=1,
            )
        if unavail is not None:
            return unavail
        return wrap_contract(
            {},
            source="kpl_theme_library",
            status="empty",
            message="KPL 题材库详情为空，未使用示例数据。",
            trade_date=trade_date,
            total=0,
        )
    except Exception as e:
        return wrap_contract(
            {},
            source="kpl_theme_library",
            status="unavailable",
            message=f"获取题材库详情失败: {str(e)}",
            trade_date=trade_date,
            total=0,
        )


@router.get("/library/{theme_id}/matched")
def theme_library_matched(theme_id: str, date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    detail_resp = theme_library_detail(theme_id, date=trade_date)
    detail = detail_resp.get("data") if isinstance(detail_resp, dict) else {}
    if not detail:
        return wrap_contract(
            {},
            source="kpl_theme_library",
            status="empty",
            message="题材库详情为空，无法生成匹配结果。",
            trade_date=trade_date,
            total=0,
        )
    return wrap_contract(
        {
            "theme_id": detail.get("theme_id") or theme_id,
            "theme_name": detail.get("theme_name") or "",
            "market_match": detail.get("market_match") or {},
            "members": detail.get("theme_sub_detail") or [],
            "quote_match_status": detail.get("quote_match_status") or "empty",
        },
        source=detail_resp.get("source") or "kpl_theme_library",
        status=detail_resp.get("data_status") or "real",
        message=detail_resp.get("message") or "",
        trade_date=trade_date,
        total=1,
    )


@router.get("/sectors/{plate_id}")
def sector_detail(plate_id: str, date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        if plate_id.startswith("mock_"):
            return wrap_contract(
                [],
                source="kpl",
                status="empty",
                trade_date=trade_date,
                count=0,
            )
        if plate_id.startswith("xgt_") or plate_id.startswith("kpl_pool_"):
            sectors = _build_sectors_from_kpl_pool(trade_date)
            for sec in sectors:
                if sec["PlateID"] == plate_id:
                    stocks = sec.get("_stocks", [])
                    detail = [
                        {"SecurityCode": s["stock_code"], "SecurityName": s["stock_name"], "ChangePercent": s["change_rate"]}
                        for s in stocks
                    ]
                    return wrap_contract(
                        detail,
                        source="kpl_pool_derived",
                        status="real",
                        trade_date=trade_date,
                        count=len(detail),
                    )
            return wrap_contract(
                [],
                source="kpl_pool_derived",
                status="empty",
                trade_date=trade_date,
                count=0,
            )
        data = _kpl.get_concept_detail(plate_id, trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None or not data:
            derived = _derive_sector_detail_from_pool(plate_id, trade_date)
            if derived:
                reason = "KPL 板块详情不可用" if unavail is not None else "KPL 板块详情为空"
                return wrap_contract(
                    derived,
                    source="kpl_pool_derived",
                    status="fallback",
                    message=f"{reason}，已用涨停池按板块名派生成员。",
                    trade_date=trade_date,
                    count=len(derived),
                )
            if unavail is not None:
                return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取板块详情失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/cycle/{theme}")
def theme_cycle(theme: str, days: int = Query(10, ge=3, le=30)):
    """
    PRD M4B-08：题材周期判断（发酵/启动/高潮/退潮/冷却/中性）。
    数据来源：theme_history 表 + data/cache/snapshot_*.json 历史快照序列。
    """
    from packages.features.theme_cycle import (
        classify_theme_phase, get_theme_history_series, PHASE_STYLE,
    )
    from apps.api.db import query_one

    # 1) appearance_days + novelty
    row = query_one("SELECT * FROM theme_history WHERE theme_name=?", (theme,))
    appearance_days = int(row["appearance_days"]) if row else 0
    first_seen = row["first_seen"] if row else None
    last_seen = row["last_seen"] if row else None
    today = datetime.now().strftime("%Y-%m-%d")
    novelty = "new" if not row else "existing"
    if row and last_seen:
        try:
            from datetime import datetime as _dt
            gap = (_dt.strptime(today, "%Y-%m-%d") - _dt.strptime(last_seen, "%Y-%m-%d")).days
            if gap >= 15:
                novelty = "revived"
        except Exception:
            pass

    # 2) 历史强度序列
    history = get_theme_history_series(theme, days=days)

    # 3) 当日数据：实时 sectors 找该题材
    today_sector = None
    try:
        sectors = _kpl.get_concept_selected(today) or []
        for s in sectors:
            name = s.get("PlateName") or s.get("concept_name") or s.get("name") or ""
            if theme in name or name in theme:
                from packages.features.theme_cycle import _extract_sector
                today_sector = _extract_sector(s)
                break
    except Exception:
        pass

    # 4) 分类
    result = classify_theme_phase(
        theme=theme,
        appearance_days=appearance_days,
        today_sector=today_sector,
        history=history,
        novelty=novelty,
    )
    style = PHASE_STYLE.get(result["phase"], {"color": "default", "icon": ""})
    has_data = bool(today_sector or history)
    result.update({
        "first_seen": first_seen,
        "last_seen": last_seen,
        "color": style["color"],
        "icon": style["icon"],
    })
    return wrap_contract(
        result,
        source="kpl",
        status="real" if has_data else "empty",
        trade_date=today,
        total=1 if has_data else 0,
        **result,
    )


@router.get("/cycle-batch")
def theme_cycle_batch(date: Optional[str] = Query(None), top: int = Query(10, ge=1, le=30)):
    """
    批量给当日 Top N 题材打周期标签（替代 mock 中的 stage 字段）。
    供复盘页"主线题材"卡 / 题材列表批量展示阶段标签。
    """
    from packages.features.theme_cycle import classify_theme_phase, get_theme_history_series, PHASE_STYLE, _extract_sector
    from apps.api.db import query_one

    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        sectors = _kpl.get_concept_selected(trade_date) or []
    except Exception:
        sectors = []
    if not sectors:
        sectors = _build_sectors_from_kpl_pool(trade_date)
    if not sectors:
        return wrap_contract(
            [],
            source="kpl_pool_derived",
            status="empty",
            trade_date=trade_date,
            total=0,
            items=[],
        )

    out: list[dict] = []
    for s in sectors[:top]:
        info = _extract_sector(s)
        name = info["name"]
        if not name:
            continue
        row = query_one("SELECT * FROM theme_history WHERE theme_name=?", (name,))
        appearance_days = int(row["appearance_days"]) if row else 0
        history = get_theme_history_series(name, days=10)
        result = classify_theme_phase(
            theme=name,
            appearance_days=appearance_days,
            today_sector=info,
            history=history,
            novelty="new" if not row else "existing",
        )
        style = PHASE_STYLE.get(result["phase"], {"color": "default", "icon": ""})
        out.append({
            "name": name,
            "phase": result["phase"],
            "icon": style["icon"],
            "color": style["color"],
            "score": result["score"],
            "appearance_days": appearance_days,
            "trend": result["trend"],
            "today_limit_up": result["today_limit_up"],
            "advice": result["advice"],
        })
    return wrap_contract(
        out,
        source="kpl",
        status="real" if out else "empty",
        trade_date=trade_date,
        total=len(out),
        items=out,
    )


@router.get("/{theme_id}")
def theme_detail(theme_id: str):
    trade_date = datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_theme_detail(theme_id) or {}
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, body={}, total=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real" if data else "empty",
            trade_date=trade_date,
            total=1 if data else 0,
        )
    except Exception as e:
        return wrap_contract(
            {},
            source="kpl",
            status="unavailable",
            message=f"获取题材详情失败: {str(e)}",
            trade_date=trade_date,
            total=0,
        )
