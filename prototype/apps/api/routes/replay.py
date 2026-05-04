from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException

from apps.api.auth import require_vip

from apps.api.utils.contract import wrap_contract
from packages.connectors.kpl.sentinel import (
    cookie_unavailable_message,
    from_client_state,
    is_cookie_missing,
    is_upstream_error,
)
from packages.connectors.registry import get_kpl
from packages.features.analysis import build_next_day_strategy
from packages.features.market import build_market_summary
from packages.features.theme import classify_board_tier, identify_leader

router = APIRouter()

_kpl = get_kpl()


def _maybe_unavailable(client, *, trade_date: str, body=None, **extra) -> Optional[dict]:
    """Return wrap_contract unavailable dict iff facade recorded a KPL sentinel.

    ``body`` defaults to ``[]`` and is the data payload returned alongside the
    contract; pass ``{}`` for endpoints that wrap a dict instead of a list
    (e.g. ``/summary``). Cookie_missing and upstream_error both surface as
    ``status='unavailable'`` so the front-end DataStatusBadge turns red and
    the operator is pointed at ``/admin``.
    """
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        [] if body is None else body,
        source="kpl",
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        **extra,
    )

# ladder/summary 快照路径，用于接力转化率与 Δ 对比
_CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_LADDER_HIST = _CACHE_DIR / "ladder_history.json"
_SUMMARY_HIST = _CACHE_DIR / "summary_history.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _save_json(path: Path, data) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _snapshot_summary(trade_date: str, summary: dict) -> None:
    """落盘 summary 快照（不覆盖已存在的同日数据，便于回测/调试）。"""
    hist = _load_json(_SUMMARY_HIST, {})
    if not isinstance(hist, dict):
        hist = {}
    if trade_date not in hist:
        hist[trade_date] = {
            "limit_up_count": summary.get("limit_up_count", 0),
            "broken_count": summary.get("broken_count", 0),
            "broken_rate": summary.get("broken_rate", 0.0),
            "seal_success_rate": summary.get("seal_success_rate", 0.0),
            "max_board": summary.get("max_board", 0),
            "sentiment_level": summary.get("sentiment_level", ""),
        }
        # 仅保留最近 60 日
        if len(hist) > 60:
            for k in sorted(hist.keys())[:-60]:
                hist.pop(k, None)
        _save_json(_SUMMARY_HIST, hist)


def _snapshot_ladder(trade_date: str, tiers: dict) -> None:
    """快照梯队：仅保存 {tier: [stock_codes]} 用于次日接力计算。"""
    hist = _load_json(_LADDER_HIST, {})
    if not isinstance(hist, dict):
        hist = {}
    compact = {}
    for tier_name, stocks in tiers.items():
        m = re.search(r"\d+", tier_name)
        numeric_key = str(m.group()) if m else tier_name
        codes = [s.get("stock_code") for s in stocks if s.get("stock_code")]
        compact[numeric_key] = codes
    hist[trade_date] = compact
    if len(hist) > 60:
        for k in sorted(hist.keys())[:-60]:
            hist.pop(k, None)
    _save_json(_LADDER_HIST, hist)


def _prev_trade_date(hist_keys: list[str], today: str) -> Optional[str]:
    earlier = sorted(k for k in hist_keys if k < today)
    return earlier[-1] if earlier else None


@router.get("/summary")
def market_summary(date: Optional[str] = Query(None), user: dict = Depends(require_vip("standard"))):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        kpl_stats = _kpl.get_market_statistics(trade_date)
        # KPL cookie-dependent call above; if sentinel surfaced, short-circuit
        # before pulling EM-public data so the contract reflects the real
        # operator-action root cause (cookie missing) rather than masking it.
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, body={}, total=0)
        if unavail is not None:
            return unavail
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        total = len(limit_up or []) + len(broken or [])
        status_total = total or len(kpl_stats or [])
        # 快照（供次日 Δ 对比）
        _snapshot_summary(trade_date, summary)
        # 注入昨日对比
        hist = _load_json(_SUMMARY_HIST, {}) or {}
        prev_date = _prev_trade_date(list(hist.keys()), trade_date)
        if prev_date:
            summary["prev_date"] = prev_date
            summary["prev"] = hist.get(prev_date, {})
        return wrap_contract(
            summary,
            source="kpl",
            status="real" if status_total else "empty",
            trade_date=trade_date,
            total=total,
            **summary,
        )
    except Exception as e:
        return wrap_contract(
            {},
            source="kpl",
            status="unavailable",
            message=f"获取市场概览失败: {str(e)}",
            trade_date=trade_date,
            total=0,
        )


@router.get("/ladder")
def board_ladder(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        data = _kpl.get_limit_up(trade_date)
        # ladder uses EM-public limit_up; sentinel will only surface here if a
        # prior call left state and get_limit_up cleared it. Belt-and-braces
        # check anyway for cookie awareness consistency across short-line.
        unavail = _maybe_unavailable(
            _kpl, trade_date=trade_date, body={}, total=0, tiers={}
        )
        if unavail is not None:
            return unavail
        tiers = classify_board_tier(data)
        result = {}
        for tier_name, stocks in sorted(tiers.items(), reverse=True):
            result[tier_name] = identify_leader(stocks)
        # 快照（供接力率计算）
        _snapshot_ladder(trade_date, result)
        return wrap_contract(
            result,
            source="kpl",
            status="real" if data else "empty",
            trade_date=trade_date,
            total=len(data or []),
            tiers=result,
        )
    except Exception as e:
        return wrap_contract(
            {},
            source="kpl",
            status="unavailable",
            message=f"获取连板天梯失败: {str(e)}",
            trade_date=trade_date,
            total=0,
            tiers={},
        )


@router.get("/ladder-relay")
def ladder_relay(date: Optional[str] = Query(None)):
    """接力转化率：昨日 N 板 → 今日 N+1 板的承接情况。

    返回结构：[{ from_tier, from_count, promoted, relay_rate, broken, broken_codes }]
    数据累积说明：依赖 ladder_history.json，需累积 ≥2 日才有意义。
    """
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        hist = _load_json(_LADDER_HIST, {}) or {}
        if trade_date not in hist:
            # 触发当日落盘
            data = _kpl.get_limit_up(trade_date)
            tiers = classify_board_tier(data)
            result = {tn: identify_leader(ss) for tn, ss in sorted(tiers.items(), reverse=True)}
            _snapshot_ladder(trade_date, result)
            hist = _load_json(_LADDER_HIST, {}) or {}

        prev_date = _prev_trade_date([k for k in hist.keys() if k != trade_date], trade_date)
        if not prev_date:
            return {
                "trade_date": trade_date,
                "prev_date": None,
                "relay": [],
                "note": "历史快照不足，需累积 ≥2 个交易日数据",
            }

        prev = hist.get(prev_date, {}) or {}
        today = hist.get(trade_date, {}) or {}

        # 今日所有涨停股代码（不分板数）→ 用于判断昨日 N 板是否今日仍涨停
        today_all_codes: set[str] = set()
        # 同时建立 code -> 今日板数 映射
        today_code_to_tier: dict[str, int] = {}
        def _parse_tier(name: str) -> Optional[int]:
            m = re.search(r"\d+", str(name))
            return int(m.group()) if m else None

        for tier_name, codes in today.items():
            n = _parse_tier(tier_name)
            if n is None:
                continue
            for c in codes:
                today_all_codes.add(c)
                today_code_to_tier[c] = max(today_code_to_tier.get(c, 0), n)

        relay = []
        for tier_name, codes in prev.items():
            n = _parse_tier(tier_name)
            if n is None:
                continue
            if not codes:
                continue
            promoted_codes = [c for c in codes if today_code_to_tier.get(c, 0) >= n + 1]
            survived_codes = [c for c in codes if c in today_all_codes and c not in promoted_codes]
            broken_codes = [c for c in codes if c not in today_all_codes]
            total = len(codes)
            promoted_rate = round(len(promoted_codes) / total * 100, 1) if total else 0.0
            relay.append({
                "from_tier": n,
                "from_count": total,
                "promoted": len(promoted_codes),
                "promoted_codes": promoted_codes[:10],
                "survived": len(survived_codes),
                "broken": len(broken_codes),
                "broken_codes": broken_codes[:10],
                "relay_rate": promoted_rate,
            })
        relay.sort(key=lambda r: r["from_tier"], reverse=True)
        return {"trade_date": trade_date, "prev_date": prev_date, "relay": relay}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取接力转化失败: {str(e)}")


@router.get("/sectors")
def sector_ranking(date: Optional[str] = Query(None)):
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        data = _kpl.get_concept_selected(trade_date)
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None:
            return unavail
        return wrap_contract(
            data,
            source="kpl",
            status="real" if data else "empty",
            trade_date=trade_date,
            count=len(data),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl",
            status="unavailable",
            message=f"获取板块排行失败: {str(e)}",
            trade_date=date or datetime.now().strftime("%Y-%m-%d"),
            count=0,
        )


@router.get("/limit-performance")
def limit_performance(date: Optional[str] = Query(None)):
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        up = _kpl.get_limit_performance(trade_date, daily_limit=True)
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, body={}, count=0)
        if unavail is not None:
            return unavail
        down = _kpl.get_limit_performance(trade_date, daily_limit=False)
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, body={}, count=0)
        if unavail is not None:
            return unavail
        return {"涨停": up, "未涨停": down}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取涨停表现失败: {str(e)}")


def _recent_trade_dates(end_date: str, n: int) -> list[str]:
    """从 end_date 倒推取 n 个交易日（简化：跳过周末，不考虑节假日）。"""
    end = datetime.strptime(end_date, "%Y-%m-%d")
    out: list[str] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:  # 0..4 = Mon..Fri
            out.append(cursor.strftime("%Y-%m-%d"))
        cursor -= timedelta(days=1)
    return out


def _extract_sector(s: dict) -> dict:
    name = s.get("PlateName") or s.get("concept_name") or s.get("col2", "")
    net = s.get("MainForce") or s.get("concept_net_amount") or s.get("col7", 0)
    amount = s.get("Amount") or s.get("concept_amount") or s.get("col6", 0)
    change = s.get("ChangePercent") or s.get("concept_increase") or s.get("col4", 0)
    intensity = s.get("Intensity") or s.get("concept_intensity") or s.get("col3", 0)
    return {
        "name": name,
        "net_flow": float(net) if net else 0.0,
        "amount": float(amount) if amount else 0.0,
        "change": float(change) if change else 0.0,
        "intensity": float(intensity) if intensity else 0.0,
    }


def _aggregate_sectors_window(end_date: str, window: int) -> list[dict]:
    """聚合近 window 个交易日的板块累计数据（按板块名累加 net_flow/amount，change 复利、intensity 取均值）。"""
    dates = _recent_trade_dates(end_date, window)
    agg: dict[str, dict] = {}
    days_seen: dict[str, int] = {}
    for d in dates:
        try:
            sectors = _kpl.get_concept_selected(d)
        except Exception:
            continue
        for s in sectors[:60]:
            it = _extract_sector(s)
            name = it["name"]
            if not name:
                continue
            cur = agg.setdefault(name, {"name": name, "net_flow": 0.0, "amount": 0.0,
                                        "change": 0.0, "intensity_sum": 0.0})
            cur["net_flow"] += it["net_flow"]
            cur["amount"] += it["amount"]
            # 复利累计：(1+r)*(1+r')-1
            cur["change"] = (1 + cur["change"] / 100) * (1 + it["change"] / 100) * 100 - 100
            cur["intensity_sum"] += it["intensity"]
            days_seen[name] = days_seen.get(name, 0) + 1
    out = []
    for name, it in agg.items():
        days = max(days_seen.get(name, 1), 1)
        out.append({
            "name": name,
            "net_flow": round(it["net_flow"], 2),
            "amount": round(it["amount"], 2),
            "change": round(it["change"], 2),
            "intensity": round(it["intensity_sum"] / days, 2),
        })
    return out


@router.get("/capital-flow")
def capital_flow(
    date: Optional[str] = Query(None),
    window: int = Query(1, ge=1, le=60, description="窗口天数：1/5/10/20/60"),
):
    """资金流向。window=1 当日；>1 累计近 N 个交易日（PRD M1-04: 5/10/20/60 日）。"""
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        if window <= 1:
            sectors = _kpl.get_concept_selected(trade_date)
            items = [_extract_sector(s) for s in sectors[:30]]
        else:
            items = _aggregate_sectors_window(trade_date, window)
        items = [it for it in items if it["name"]]
        items.sort(key=lambda x: abs(x["net_flow"]), reverse=True)
        return {"count": len(items[:30]), "window": window, "data": items[:30]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资金流向失败: {str(e)}")


@router.get("/rotation")
def sector_rotation(
    date: Optional[str] = Query(None),
    window: int = Query(1, ge=1, le=10, description="板块轮动视角：1/3/5/10 日"),
):
    """板块轮动散点。window=1 当日；>1 累计近 N 个交易日（PRD M2-01: 1/3/5/10 日）。"""
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        if window <= 1:
            sectors = _kpl.get_concept_selected(trade_date)
            points = [_extract_sector(s) for s in sectors[:40]]
        else:
            points = _aggregate_sectors_window(trade_date, window)[:40]
        return {"count": len(points), "window": window, "data": points}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取板块轮动失败: {str(e)}")


@router.get("/archive")
def replay_archive(
    keyword: Optional[str] = Query(None, description="关键词：日期片段 / 情绪等级 / 题材名"),
    sentiment: Optional[str] = Query(None, description="情绪过滤：高潮/回暖/中性/低迷/冰点"),
    limit: int = Query(60, ge=1, le=365),
):
    """
    PRD M1-07：历史复盘存档列表。
    基于 summary_history.json 反向遍历，支持关键词模糊搜索与情绪过滤。
    """
    try:
        hist = _load_json(_SUMMARY_HIST, {}) or {}
        if not isinstance(hist, dict):
            return {"total": 0, "items": []}

        items = []
        for d in sorted(hist.keys(), reverse=True):
            s = hist[d] or {}
            row = {
                "trade_date": d,
                "sentiment_level": s.get("sentiment_level", ""),
                "sentiment_score": s.get("sentiment_score", 0),
                "limit_up_count": s.get("limit_up_count", 0),
                "max_board": s.get("max_board", 0),
                "broken_count": s.get("broken_count", 0),
                "broken_rate": s.get("broken_rate", 0),
                "seal_success_rate": s.get("seal_success_rate", 0),
            }
            # 过滤
            if sentiment and row["sentiment_level"] != sentiment:
                continue
            if keyword:
                blob = f"{d} {row['sentiment_level']}"
                if keyword.lower() not in blob.lower():
                    continue
            items.append(row)
            if len(items) >= limit:
                break
        return {"total": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取复盘存档失败: {str(e)}")


@router.get("/next-day-strategy")
def next_day_strategy(date: Optional[str] = Query(None), user: dict = Depends(require_vip("standard"))):
    """
    PRD M4A-08：次日开盘策略 · 三场景结构化输出（溢价 / 低吸 / 排板）。
    聚合当日 summary + ladder + sectors，输出可直接渲染的策略卡片数据。
    """
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        # summary
        kpl_stats = _kpl.get_market_statistics(trade_date)
        limit_up = _kpl.get_limit_up(trade_date)
        broken = _kpl.get_broken(trade_date)
        summary = build_market_summary(kpl_stats, limit_up, broken)
        # ladder
        tiers_raw = classify_board_tier(limit_up)
        tiers = {k: identify_leader(v) for k, v in tiers_raw.items()}
        ladder = {"tiers": tiers}
        # sectors
        sectors = _kpl.get_concept_selected(trade_date)[:40]
        # 标准化 sector 字段名供 _pick_top_themes 使用
        sectors_norm = [{
            "name": _extract_sector(s)["name"],
            "intensity": _extract_sector(s)["intensity"],
        } for s in sectors]
        sectors_norm.sort(key=lambda x: x["intensity"], reverse=True)

        return build_next_day_strategy(summary, ladder, sectors_norm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成次日策略失败: {str(e)}")
