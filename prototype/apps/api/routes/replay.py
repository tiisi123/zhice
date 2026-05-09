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


def _candidate_prev_trade_dates(today: str, lookback_days: int = 10) -> list[str]:
    """Return recent calendar days before today, skipping weekends."""
    try:
        cursor = datetime.strptime(today, "%Y-%m-%d").date()
    except ValueError:
        return []

    dates: list[str] = []
    offset = 1
    while len(dates) < lookback_days and offset <= lookback_days * 2:
        d = cursor - timedelta(days=offset)
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        offset += 1
    return dates


def _snapshot_ladder_from_kpl(trade_date: str) -> bool:
    data = _kpl.get_limit_up(trade_date)
    if not data:
        return False
    tiers = classify_board_tier(data)
    result = {tn: identify_leader(ss) for tn, ss in sorted(tiers.items(), reverse=True)}
    _snapshot_ladder(trade_date, result)
    return True


def _ensure_ladder_prev_snapshot(trade_date: str, hist: dict) -> dict:
    if _prev_trade_date([k for k in hist.keys() if k != trade_date], trade_date):
        return hist

    for candidate in _candidate_prev_trade_dates(trade_date):
        if candidate in hist:
            return hist
        if _snapshot_ladder_from_kpl(candidate):
            refreshed = _load_json(_LADDER_HIST, {}) or {}
            if candidate in refreshed:
                return refreshed
    return hist


def _parse_tier_num(name: str) -> Optional[int]:
    m = re.search(r"\d+", str(name))
    return int(m.group()) if m else None


def _calc_promotion_stats(
    today_tiers: dict, hist: dict, trade_date: str,
) -> dict[str, dict]:
    prev_date = _prev_trade_date(
        [k for k in hist if k != trade_date], trade_date,
    )
    if not prev_date:
        return {}

    prev_day = hist.get(prev_date) or {}
    today_snap = hist.get(trade_date) or {}

    today_codes_by_tier: dict[int, set[str]] = {}
    for tier_name, codes in today_snap.items():
        n = _parse_tier_num(tier_name)
        if n is not None:
            today_codes_by_tier.setdefault(n, set()).update(codes)

    stats: dict[str, dict] = {}
    for tier_name, stocks in today_tiers.items():
        n = _parse_tier_num(tier_name)
        if n is None or n < 2:
            stats[tier_name] = {
                "promotion_rate": None,
                "promoted_count": 0,
                "from_count": 0,
            }
            continue
        prev_lower = set(prev_day.get(str(n - 1), []))
        if not prev_lower:
            stats[tier_name] = {
                "promotion_rate": None,
                "promoted_count": 0,
                "from_count": 0,
            }
            continue
        promoted = prev_lower & today_codes_by_tier.get(n, set())
        from_count = len(prev_lower)
        stats[tier_name] = {
            "promotion_rate": round(len(promoted) / from_count * 100, 1),
            "promoted_count": len(promoted),
            "from_count": from_count,
        }
    return stats


def _calc_sector_concentration(stocks: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for s in stocks:
        sectors = s.get("related_plates") or (
            [s["first_plate_name"]] if s.get("first_plate_name") else []
        )
        for sec in sectors:
            name = sec if isinstance(sec, str) else str(sec)
            if name:
                counts[name] = counts.get(name, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    return [{"name": n, "count": c} for n, c in ranked]


def _sector_names_from_stock(stock: dict) -> set[str]:
    names: set[str] = set()
    related = stock.get("related_plates") or []
    if isinstance(related, str):
        related = [x.strip() for x in related.replace("、", ",").split(",") if x.strip()]
    for item in related:
        if isinstance(item, dict):
            name = item.get("name") or item.get("plate_name") or item.get("concept_name")
        else:
            name = str(item)
        if name:
            names.add(str(name).strip())
    first = stock.get("first_plate_name")
    if first:
        names.add(str(first).strip())
    return {n for n in names if n}


_SECTOR_MEMBER_ALIASES: dict[str, tuple[str, ...]] = {
    "算力": ("计算机", "通信", "光通信", "光模块", "数据中心", "服务器", "PCB", "CPO"),
    "通信": ("通信", "光通信", "光模块", "CPO", "5G", "6G"),
    "机器人概念": ("机器人", "自动化", "通用设备", "专用设备", "电机", "机械"),
    "机器人": ("机器人", "自动化", "通用设备", "专用设备", "电机", "机械"),
    "芯片": ("芯片", "半导体", "集成电路", "元件", "光学光电", "电子"),
    "AI应用": ("AI", "人工智能", "软件", "传媒", "游戏", "互联网"),
}


def _norm_sector_name(name: str) -> str:
    return re.sub(r"[\s（）()概念板块ⅡⅠ]+", "", name).lower()


def _sector_matches_stock(sector_names: set[str], stock_names: set[str]) -> bool:
    sector_tokens: set[str] = set()
    for name in sector_names:
        norm = _norm_sector_name(name)
        if norm:
            sector_tokens.add(norm)
        for alias in _SECTOR_MEMBER_ALIASES.get(name, ()):
            alias_norm = _norm_sector_name(alias)
            if alias_norm:
                sector_tokens.add(alias_norm)

    stock_tokens = {_norm_sector_name(name) for name in stock_names}
    stock_tokens = {name for name in stock_tokens if name}
    for sector_token in sector_tokens:
        for stock_token in stock_tokens:
            if sector_token == stock_token or sector_token in stock_token or stock_token in sector_token:
                return True
    return False


def _enrich_sectors_with_limit_members(sectors: list[dict], limit_up: list[dict]) -> list[dict]:
    if not sectors or not limit_up:
        return sectors

    enriched: list[dict] = []
    for sector in sectors:
        names = {
            str(
                sector.get("name")
                or sector.get("first_plate_name")
                or sector.get("PlateName")
                or sector.get("concept_name")
                or sector.get("col2")
                or ""
            ).strip()
        }
        names = {n for n in names if n}
        members = [
            stock for stock in limit_up
            if _sector_matches_stock(names, _sector_names_from_stock(stock))
        ]
        item = dict(sector)
        item["limit_up_members"] = members[:20]
        item["limit_up_count"] = len(members)
        enriched.append(item)
    return enriched


def _build_sectors_from_limit_up(limit_up: list[dict]) -> list[dict]:
    plate_map: dict[str, list[dict]] = {}
    for stock in limit_up or []:
        names = _sector_names_from_stock(stock)
        for name in names:
            plate_map.setdefault(name, []).append(stock)

    rows: list[dict] = []
    for idx, (name, members) in enumerate(
        sorted(plate_map.items(), key=lambda item: len(item[1]), reverse=True)
    ):
        changes = [
            float(stock.get("change_rate") or 0)
            for stock in members
            if stock.get("change_rate") is not None
        ]
        avg_change = round(sum(changes) / len(changes), 2) if changes else 0.0
        board_max = max((int(stock.get("board_count") or 1) for stock in members), default=1)
        intensity = len(members) * 100 + board_max * 10
        amount = sum(float(stock.get("amount") or stock.get("seal_amount") or 0) for stock in members)
        rows.append({
            "PlateID": f"kpl_pool_{idx}",
            "name": name,
            "PlateName": name,
            "concept_name": name,
            "first_plate_name": name,
            "ChangePercent": avg_change,
            "change_rate": avg_change,
            "concept_increase": avg_change,
            "Intensity": intensity,
            "intensity": intensity,
            "concept_intensity": intensity,
            "MainForce": amount,
            "net_flow": amount,
            "concept_net_amount": amount,
            "Amount": amount,
            "amount": amount,
            "concept_amount": amount,
            "LimitUpNum": len(members),
            "limit_up_count": len(members),
            "limit_up_members": members[:20],
        })
    return rows


@router.get("/summary")
def market_summary(date: Optional[str] = Query(None), user: dict = Depends(require_vip("standard"))):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        kpl_stats = _kpl.get_market_statistics(trade_date)
        kpl_stats_message = ""
        if from_client_state(_kpl):
            kpl_stats_message = "KPL 市场统计不可用，复盘已使用东财涨停/炸板公开池降级展示。"
            kpl_stats = []
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
            message=kpl_stats_message,
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
        unavail = _maybe_unavailable(
            _kpl, trade_date=trade_date, body={}, total=0, tiers={}
        )
        if unavail is not None:
            return unavail
        tiers = classify_board_tier(data)
        result = {}
        for tier_name, stocks in sorted(tiers.items(), reverse=True):
            result[tier_name] = identify_leader(stocks)
        _snapshot_ladder(trade_date, result)

        hist = _load_json(_LADDER_HIST, {}) or {}
        promo_stats = _calc_promotion_stats(result, hist, trade_date)

        tier_stats = {}
        for tier_name, stocks in result.items():
            tier_promo = promo_stats.get(tier_name, {})
            tier_stats[tier_name] = {
                "promotion_rate": tier_promo.get("promotion_rate"),
                "promoted_count": tier_promo.get("promoted_count", 0),
                "from_count": tier_promo.get("from_count", 0),
                "top_sectors": _calc_sector_concentration(stocks),
            }

        return wrap_contract(
            result,
            source="kpl",
            status="real" if data else "empty",
            trade_date=trade_date,
            total=len(data or []),
            tiers=result,
            tier_stats=tier_stats,
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
            _snapshot_ladder_from_kpl(trade_date)
            hist = _load_json(_LADDER_HIST, {}) or {}

        hist = _ensure_ladder_prev_snapshot(trade_date, hist)
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
        limit_up = _kpl.get_limit_up(trade_date)
        if data:
            data = _enrich_sectors_with_limit_members(data, limit_up)
            source = "kpl"
        else:
            data = _build_sectors_from_limit_up(limit_up)
            source = "kpl_pool_derived"
        unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
        if unavail is not None and not data:
            return unavail
        return wrap_contract(
            data,
            source=source,
            status="real" if data else "empty",
            message="KPL 概念板块接口不可用，已用涨停池派生主线。" if source == "kpl_pool_derived" and data else "",
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
        if not sectors:
            sectors = _build_sectors_from_limit_up(_kpl.get_limit_up(d))
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


def _query_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        default = getattr(value, "default", fallback)
        try:
            return int(default)
        except (TypeError, ValueError):
            return fallback


@router.get("/capital-flow")
def capital_flow(
    date: Optional[str] = Query(None),
    window: int = Query(1, ge=1, le=60, description="窗口天数：1/5/10/20/60"),
):
    """资金流向。window=1 当日；>1 累计近 N 个交易日（PRD M1-04: 5/10/20/60 日）。"""
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        window = _query_int(window, 1)
        source = "kpl"
        message = ""
        if window <= 1:
            sectors = _kpl.get_concept_selected(trade_date)
            if not sectors:
                sectors = _build_sectors_from_limit_up(_kpl.get_limit_up(trade_date))
                if sectors:
                    source = "kpl_pool_derived"
                    message = "KPL 概念板块接口不可用，已用涨停池派生资金信号。"
            items = [_extract_sector(s) for s in sectors[:30]]
        else:
            items = _aggregate_sectors_window(trade_date, window)
        items = [it for it in items if it["name"]]
        items.sort(key=lambda x: abs(x["net_flow"]), reverse=True)
        data = items[:30]
        return wrap_contract(
            data,
            source=source,
            status="real" if data else "empty",
            message=message,
            trade_date=trade_date,
            count=len(data),
            window=window,
        )
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
        window = _query_int(window, 1)
        source = "kpl"
        message = ""
        if window <= 1:
            sectors = _kpl.get_concept_selected(trade_date)
            if not sectors:
                sectors = _build_sectors_from_limit_up(_kpl.get_limit_up(trade_date))
                if sectors:
                    source = "kpl_pool_derived"
                    message = "KPL 概念板块接口不可用，已用涨停池派生轮动信号。"
            points = [_extract_sector(s) for s in sectors[:40]]
        else:
            points = _aggregate_sectors_window(trade_date, window)[:40]
        return wrap_contract(
            points,
            source=source,
            status="real" if points else "empty",
            message=message,
            trade_date=trade_date,
            count=len(points),
            window=window,
        )
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
        if sectors:
            sectors = _enrich_sectors_with_limit_members(sectors, limit_up)
        else:
            sectors = _build_sectors_from_limit_up(limit_up)
        # 标准化 sector 字段名供 _pick_top_themes 使用
        sectors_norm = [{
            "name": _extract_sector(s)["name"],
            "intensity": _extract_sector(s)["intensity"],
            "limit_up_members": s.get("limit_up_members") or [],
            "limit_up_count": s.get("limit_up_count") or 0,
        } for s in sectors]
        sectors_norm.sort(key=lambda x: x["intensity"], reverse=True)

        result = build_next_day_strategy(summary, ladder, sectors_norm)
        return wrap_contract(
            result,
            source="kpl",
            status="real",
            trade_date=trade_date,
            **result,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成次日策略失败: {str(e)}")
