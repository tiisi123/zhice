from __future__ import annotations

from datetime import datetime
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


@router.get("/list")
def theme_list(date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        data = _kpl.get_theme_list(trade_date) or []
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
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
            message=f"获取题材列表失败: {str(e)}",
            trade_date=trade_date,
            count=0,
        )


@router.get("/sectors")
def sector_list(date: Optional[str] = Query(None)):
    trade_date = _trade_date(date)
    try:
        data = _kpl.get_concept_selected(trade_date)
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        source = "kpl"
        if not data:
            data = _build_sectors_from_kpl_pool(trade_date)
            source = "kpl_pool_derived"
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
        return wrap_contract(
            [],
            source="kpl",
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
