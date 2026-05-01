"""M2-05 / M4B-07 轮动推演模拟 + M4B-09 预期差 + M4B-10 新题材 + M4B-11 题材历史复盘。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from apps.api.utils.contract import wrap_contract
from packages.connectors.kpl.sentinel import (
    cookie_unavailable_message,
    from_client_state,
    is_cookie_missing,
    is_upstream_error,
)
from packages.connectors.registry import get_kpl
from packages.features.theme_novelty import mark_themes, list_recent_new
from packages.features.expectation import batch_evaluate, evaluate

router = APIRouter()

_kpl = get_kpl()


def _maybe_unavailable(client, *, trade_date: str, **extra) -> dict | None:
    sentinel = from_client_state(client)
    if not sentinel:
        return None
    if not (is_cookie_missing(sentinel) or is_upstream_error(sentinel)):
        return None
    return wrap_contract(
        [],
        source="kpl",
        status="unavailable",
        message=cookie_unavailable_message(sentinel),
        trade_date=trade_date,
        **extra,
    )


# 常见产业链/主题传导矩阵（简化版，可持续扩充）
TRANSMISSION_MAP: dict[str, list[tuple[str, float, int]]] = {
    # 触发题材 -> [(受益题材, 传导概率, 平均滞后天数)]
    "AI算力": [("光模块", 0.75, 1), ("液冷", 0.65, 2), ("服务器", 0.7, 1), ("铜连接", 0.55, 3)],
    "光模块": [("CPO", 0.6, 1), ("芯片", 0.4, 2), ("PCB", 0.5, 2)],
    "新能源车": [("锂电池", 0.8, 1), ("碳化硅", 0.55, 2), ("充电桩", 0.6, 2)],
    "机器人": [("减速器", 0.7, 1), ("伺服电机", 0.65, 1), ("丝杠", 0.6, 2), ("传感器", 0.5, 2)],
    "存储芯片": [("HBM", 0.75, 1), ("封测", 0.6, 2), ("存储模组", 0.55, 2)],
    "固态电池": [("电解质", 0.75, 1), ("锂电设备", 0.5, 2), ("正极材料", 0.6, 2)],
    "低空经济": [("eVTOL", 0.7, 1), ("通用航空", 0.6, 2), ("无人机", 0.65, 2)],
    "减肥药": [("CXO", 0.55, 2), ("多肽", 0.7, 1), ("原料药", 0.5, 3)],
    "军工": [("军工电子", 0.7, 1), ("航空发动机", 0.6, 2), ("军工信息化", 0.6, 2)],
}


class SimulateIn(BaseModel):
    trigger_theme: str
    days: int = 3


@router.post("/simulate")
def simulate(inp: SimulateIn):
    """假设某题材启动，预测 N 日内潜在跟涨题材概率。"""
    trigger = inp.trigger_theme.strip()
    direct = TRANSMISSION_MAP.get(trigger, [])
    # 二阶传导
    indirect: dict[str, tuple[float, int]] = {}
    for name, p, lag in direct:
        for name2, p2, lag2 in TRANSMISSION_MAP.get(name, []):
            if name2 == trigger:
                continue
            combined_p = round(p * p2, 3)
            combined_lag = lag + lag2
            if name2 in indirect:
                if combined_p > indirect[name2][0]:
                    indirect[name2] = (combined_p, combined_lag)
            else:
                indirect[name2] = (combined_p, combined_lag)
    direct_list = [
        {"theme": n, "probability": p, "avg_lag_days": lag}
        for n, p, lag in direct
    ]
    indirect_list = [
        {"theme": n, "probability": p, "avg_lag_days": lag}
        for n, (p, lag) in sorted(indirect.items(), key=lambda x: -x[1][0])
    ]
    payload = {
        "trigger": trigger,
        "direct": direct_list,
        "indirect": indirect_list,
        "known_themes": sorted(TRANSMISSION_MAP.keys()),
        "output_type": "rule_inference",
    }
    return wrap_contract(
        payload,
        source="transmission_rule_matrix",
        status="real" if (direct_list or indirect_list) else "empty",
        **payload,
    )


@router.get("/known-themes")
def known_themes():
    themes = sorted(TRANSMISSION_MAP.keys())
    return wrap_contract(
        themes,
        source="transmission_rule_matrix",
        status="real",
        themes=themes,
        output_type="rule_inference",
    )


@router.get("/novelty")
def novelty(date: Optional[str] = Query(None), days: int = 3):
    """M4B-10 识别最近的新题材 / 重新激活题材。"""
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    sectors = _kpl.get_concept_selected(trade_date) or []
    unavail = _maybe_unavailable(_kpl, trade_date=trade_date, count=0)
    if unavail is not None:
        return unavail
    marked = mark_themes(sectors, trade_date)
    return wrap_contract(
        marked,
        source="kpl",
        status="real" if marked else "empty",
        trade_date=trade_date,
        themes=marked,
        new_recent=list_recent_new(days=days),
    )


class GapIn(BaseModel):
    news: str
    change_rate: float = 0.0
    vol_ratio: float = 1.0


@router.post("/expectation-gap")
def expectation_gap(inp: GapIn):
    result = evaluate(inp.news, inp.change_rate, inp.vol_ratio)
    return wrap_contract(
        result,
        source="expectation_rule_model",
        status="real",
        output_type="rule_score",
        **result,
    )


class BatchGapIn(BaseModel):
    items: list[dict]


@router.post("/expectation-gap/batch")
def expectation_gap_batch(inp: BatchGapIn):
    items = batch_evaluate(inp.items)
    return wrap_contract(
        items,
        source="expectation_rule_model",
        status="real" if items else "empty",
        items=items,
        output_type="rule_score",
    )


@router.get("/theme-history/{theme}")
def theme_history(theme: str, days: int = 90):
    """M4B-11 题材历史复盘：给定题材名，拉取该题材最近 N 日涨停/热度轨迹。"""
    end = datetime.now()
    traj: list[dict] = []
    for i in range(days, -1, -1):
        d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
        if d.endswith(("-01", "-08", "-15", "-22")) is False and i != 0:
            continue
        sectors = _kpl.get_concept_selected(d) or []
        unavail = _maybe_unavailable(_kpl, trade_date=d, theme=theme, trajectory=[])
        if unavail is not None:
            return unavail
        match = None
        for s in sectors:
            if theme in (s.get("PlateName") or s.get("name") or ""):
                match = s
                break
        if match:
            traj.append({
                "date": d,
                "intensity": match.get("Intensity") or match.get("intensity") or 0,
                "change_rate": match.get("ChangePercent") or match.get("change_rate") or 0,
            })
    return wrap_contract(
        traj,
        source="kpl",
        status="real" if traj else "empty",
        theme=theme,
        trajectory=traj,
    )
