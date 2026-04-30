"""M2-05 / M4B-07 轮动推演模拟 + M4B-09 预期差 + M4B-10 新题材 + M4B-11 题材历史复盘。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from packages.connectors.registry import get_kpl
from packages.features.theme_novelty import mark_themes, list_recent_new
from packages.features.expectation import batch_evaluate, evaluate

router = APIRouter()

_kpl = get_kpl()

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
    result = {
        "trigger": trigger,
        "direct": [
            {"theme": n, "probability": p, "avg_lag_days": lag}
            for n, p, lag in direct
        ],
        "indirect": [
            {"theme": n, "probability": p, "avg_lag_days": lag}
            for n, (p, lag) in sorted(indirect.items(), key=lambda x: -x[1][0])
        ],
        "known_themes": sorted(TRANSMISSION_MAP.keys()),
        "source": "transmission_rule_matrix",
        "output_type": "rule_inference",
        "data_status": "ok" if direct or indirect else "empty",
    }
    return result


@router.get("/known-themes")
def known_themes():
    return {
        "themes": sorted(TRANSMISSION_MAP.keys()),
        "source": "transmission_rule_matrix",
        "output_type": "rule_inference",
        "data_status": "ok",
    }


@router.get("/novelty")
def novelty(date: Optional[str] = Query(None), days: int = 3):
    """M4B-10 识别最近的新题材 / 重新激活题材。"""
    try:
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        sectors = _kpl.get_concept_selected(trade_date) or []
        marked = mark_themes(sectors, trade_date)
        return {
            "trade_date": trade_date,
            "themes": marked,
            "new_recent": list_recent_new(days=days),
            "source": "kpl",
            "data_status": "ok" if marked else "empty",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"新题材识别失败: {e}")


class GapIn(BaseModel):
    news: str
    change_rate: float = 0.0
    vol_ratio: float = 1.0


@router.post("/expectation-gap")
def expectation_gap(inp: GapIn):
    result = evaluate(inp.news, inp.change_rate, inp.vol_ratio)
    result.update({"source": "expectation_rule_model", "output_type": "rule_score", "data_status": "ok"})
    return result


class BatchGapIn(BaseModel):
    items: list[dict]


@router.post("/expectation-gap/batch")
def expectation_gap_batch(inp: BatchGapIn):
    return {
        "items": batch_evaluate(inp.items),
        "source": "expectation_rule_model",
        "output_type": "rule_score",
        "data_status": "ok",
    }


@router.get("/theme-history/{theme}")
def theme_history(theme: str, days: int = 90):
    """M4B-11 题材历史复盘：给定题材名，拉取该题材最近 N 日涨停/热度轨迹。"""
    try:
        end = datetime.now()
        traj = []
        for i in range(days, -1, -1):
            d = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            if d.endswith(("-01", "-08", "-15", "-22")) is False and i != 0:
                continue  # 只取部分采样点，避免拉爆外部接口
            try:
                sectors = _kpl.get_concept_selected(d) or []
            except Exception:
                continue
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
        return {
            "theme": theme,
            "trajectory": traj,
            "source": "kpl",
            "data_status": "ok" if traj else "empty",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"题材复盘失败: {e}")
