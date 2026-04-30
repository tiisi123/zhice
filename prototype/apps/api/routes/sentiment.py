from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from apps.api.utils.contract import wrap_contract
from packages.connectors.registry import get_kpl
from packages.features.market import build_market_summary

router = APIRouter()

_kpl = get_kpl()

_HIST_PATH = Path(__file__).parent.parent.parent.parent / "data" / "cache" / "sentiment_history.json"

def _load_history() -> list[dict]:
    if _HIST_PATH.exists():
        try:
            records = json.loads(_HIST_PATH.read_text(encoding="utf-8"))
            if records:
                return records
        except Exception:
            pass
    return []


@router.get("/sentiment-history")
def sentiment_history(days: int = Query(30)):
    try:
        history_path = Path(__file__).parent.parent.parent.parent / "data" / "cache" / "sentiment_history.json"
        records: list[dict] = []
        if history_path.exists():
            try:
                records = json.loads(history_path.read_text(encoding="utf-8"))
            except Exception:
                records = []

        trade_date = datetime.now().strftime("%Y-%m-%d")
        existing_dates = {r["date"] for r in records}
        if trade_date not in existing_dates:
            try:
                limit_up = _kpl.get_limit_up(trade_date)
                broken = _kpl.get_broken(trade_date)
                summary = build_market_summary(_kpl.get_market_statistics(trade_date), limit_up, broken)
                record = {
                    "date": trade_date,
                    "limit_up": summary["limit_up_count"],
                    "broken": summary["broken_count"],
                    "broken_rate": summary["broken_rate"],
                    "max_board": summary["max_board"],
                    "sentiment": summary["sentiment_level"],
                    "score": summary["sentiment_score"],
                    "up": summary["up_count"],
                    "down": summary["down_count"],
                }
                records.append(record)
                records.sort(key=lambda x: x["date"])
                history_path.parent.mkdir(parents=True, exist_ok=True)
                history_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        recent = records[-days:] if len(records) > days else records
        return wrap_contract(
            recent,
            source="kpl_sentiment",
            status="real",
            count=len(recent),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl_sentiment",
            status="unavailable",
            message=f"获取情绪历史失败: {str(e)}",
            count=0,
        )


# ==================== 周期相位定位 ====================
_PHASE_ORDER = ["冰点", "筑底", "回升", "高潮", "顶背离", "退潮"]


def _infer_phase(records: list[dict]) -> dict:
    """基于最近 5 日的序列推断当前周期相位。"""
    if not records:
        return {"phase": "未知", "confidence": 0.0, "basis": "无历史数据"}
    last5 = records[-5:]
    latest = last5[-1]
    sent = latest.get("sentiment", "")
    lu = latest.get("limit_up", 0) or 0
    mb = latest.get("max_board", 0) or 0

    lus = [r.get("limit_up", 0) or 0 for r in last5]
    # 斜率：最近 3 日趋势
    tail = lus[-3:] if len(lus) >= 3 else lus
    slope = (tail[-1] - tail[0]) / max(1, len(tail) - 1) if len(tail) >= 2 else 0.0

    if sent == "高潮":
        phase = "高潮"
    elif sent == "冰点":
        phase = "冰点"
    elif sent == "回暖" and slope > 5:
        phase = "回升"
    elif sent == "回暖" and slope <= 5 and any(r.get("sentiment") == "高潮" for r in last5):
        phase = "顶背离"
    elif sent == "低迷" and any(r.get("sentiment") in ("高潮", "回暖") for r in last5) and slope < 0:
        phase = "退潮"
    elif sent == "低迷" and slope > 0:
        phase = "筑底"
    elif sent == "中性":
        phase = "回升" if slope > 0 else "退潮" if slope < 0 else "中性"
    else:
        phase = sent or "中性"

    # 置信度：基于最近 5 日同相位占比 + 斜率显著性
    conf_base = 0.5 + min(abs(slope) / 20.0, 0.4)
    basis = f"近5日涨停 {lus}，斜率 {slope:.1f}/日，最新情绪「{sent}」，最高 {mb}板"

    return {
        "phase": phase,
        "confidence": round(min(conf_base, 0.95), 2),
        "slope": round(slope, 2),
        "basis": basis,
        "recent": last5,
    }


@router.get("/sentiment-phase")
def sentiment_phase():
    try:
        records = _load_history()
        phase = _infer_phase(records)
        status = "empty" if not records else "real"
        return wrap_contract(
            phase,
            source="kpl_sentiment",
            status=status,
            **phase,
        )
    except Exception as e:
        return wrap_contract(
            {},
            source="kpl_sentiment",
            status="unavailable",
            message=f"相位推断失败: {str(e)}",
            phase="未知",
            confidence=0.0,
            basis="推断异常",
        )


# ==================== 历史相似日检索 ====================
def _distance(a: dict, b: dict) -> float:
    """特征归一化欧氏距离（涨停、炸板率、最高板、情绪分）。"""
    def norm_lu(x): return (x or 0) / 100.0
    def norm_br(x): return (x or 0) / 50.0
    def norm_mb(x): return (x or 0) / 8.0
    def norm_sc(x): return (x or 0) / 100.0
    d = (
        (norm_lu(a.get("limit_up")) - norm_lu(b.get("limit_up"))) ** 2
        + (norm_br(a.get("broken_rate")) - norm_br(b.get("broken_rate"))) ** 2
        + (norm_mb(a.get("max_board")) - norm_mb(b.get("max_board"))) ** 2
        + (norm_sc(a.get("score")) - norm_sc(b.get("score"))) ** 2
    )
    base = math.sqrt(d)
    # 情绪等级不一致时加权
    if a.get("sentiment") != b.get("sentiment"):
        base += 0.15
    return base


@router.get("/similar-days")
def similar_days(
    date: Optional[str] = Query(None),
    top_k: int = Query(5),
    forward: int = Query(5, description="查看后续 N 个交易日表现"),
):
    """返回历史上与目标日最相似的 K 日，及各相似日之后 N 日的走势。"""
    try:
        records = _load_history()
        if len(records) < 10:
            return wrap_contract(
                [],
                source="kpl_sentiment",
                status="empty",
                message=f"历史样本不足（{len(records)} 日），需累积 ≥10 日",
                target=None,
                matches=[],
                note=f"历史样本不足（{len(records)} 日），需累积 ≥10 日",
            )
        idx_by_date = {r["date"]: i for i, r in enumerate(records)}
        target_date = date or records[-1]["date"]
        if target_date not in idx_by_date:
            target_date = records[-1]["date"]
        t_idx = idx_by_date[target_date]
        target = records[t_idx]

        # 候选：排除目标日前后 ±2 日（避免自相关）
        scored = []
        for i, r in enumerate(records):
            if abs(i - t_idx) <= 2:
                continue
            scored.append((_distance(target, r), i, r))
        scored.sort(key=lambda x: x[0])
        top = scored[:top_k]

        matches = []
        for dist, i, r in top:
            # 后续 forward 日的表现
            forward_records = records[i + 1 : i + 1 + forward]
            fwd_lu_avg = (
                round(sum((x.get("limit_up", 0) or 0) for x in forward_records) / len(forward_records), 1)
                if forward_records else None
            )
            fwd_mb_max = (
                max((x.get("max_board", 0) or 0) for x in forward_records)
                if forward_records else None
            )
            # 情绪走向：后 N 日情绪标签分布
            fwd_sentiments = [x.get("sentiment") for x in forward_records]

            matches.append({
                "date": r["date"],
                "distance": round(dist, 4),
                "snapshot": {
                    "limit_up": r.get("limit_up"),
                    "broken": r.get("broken"),
                    "broken_rate": r.get("broken_rate"),
                    "max_board": r.get("max_board"),
                    "sentiment": r.get("sentiment"),
                },
                "forward": {
                    "days": len(forward_records),
                    "dates": [x["date"] for x in forward_records],
                    "limit_up_series": [x.get("limit_up", 0) for x in forward_records],
                    "max_board_series": [x.get("max_board", 0) for x in forward_records],
                    "sentiment_series": fwd_sentiments,
                    "limit_up_avg": fwd_lu_avg,
                    "max_board_peak": fwd_mb_max,
                },
            })

        return wrap_contract(
            matches,
            source="kpl_sentiment",
            status="real",
            target={"date": target_date, **target},
            matches=matches,
            count=len(matches),
        )
    except Exception as e:
        return wrap_contract(
            [],
            source="kpl_sentiment",
            status="unavailable",
            message=f"相似日检索失败: {str(e)}",
            target=None,
            matches=[],
            count=0,
        )
