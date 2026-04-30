"""M4B-09 预期差评估：按「利好强度 × 股价反映程度」量化。"""
from __future__ import annotations

from typing import Any

# 利好强度关键词映射（0-1）
IMPACT_KEYWORDS = {
    "政策": 0.85,
    "补贴": 0.8,
    "招标": 0.65,
    "订单": 0.7,
    "中标": 0.75,
    "合作": 0.5,
    "收购": 0.75,
    "借壳": 0.9,
    "新品": 0.55,
    "产能": 0.5,
    "业绩预增": 0.8,
    "分红": 0.3,
    "回购": 0.45,
}


def score_impact(text: str) -> float:
    text = text or ""
    s = 0.0
    for k, w in IMPACT_KEYWORDS.items():
        if k in text:
            s = max(s, w)
    return s


def evaluate(news: str, change_rate_after: float, vol_ratio: float = 1.0) -> dict[str, Any]:
    impact = score_impact(news)
    # 股价反应归一：单日涨幅 10% ≈ 满反应；量比放大 2x 也加权
    reaction = max(0.0, min(1.0, change_rate_after / 10.0))
    reaction = min(1.0, reaction + max(0.0, (vol_ratio - 1.0)) * 0.1)
    gap = impact - reaction
    if gap > 0.25:
        label = "预期差正向（利好未充分兑现）"
    elif gap < -0.25:
        label = "预期差负向（反应过度）"
    else:
        label = "基本对价"
    return {
        "impact": round(impact, 2),
        "reaction": round(reaction, 2),
        "gap": round(gap, 2),
        "label": label,
    }


def batch_evaluate(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        res = evaluate(
            it.get("news", ""),
            float(it.get("change_rate", 0) or 0),
            float(it.get("vol_ratio", 1) or 1),
        )
        out.append({**it, **res})
    out.sort(key=lambda x: x["gap"], reverse=True)
    return out
