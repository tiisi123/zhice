"""
PRD M4B-08 · 题材周期判断
========================

输入：题材名（与 sectors[*].PlateName/concept_name/name 对齐）
判定五阶段：发酵 → 启动 → 高潮 → 退潮 → 冷却（外加"中性"分歧态）

判定依据：
  1. appearance_days：来自 theme_history 表，从首次出现至今的活跃天数
  2. 近 N 日强度趋势：从 data/cache/snapshot_*.json 抽取该题材每日 intensity / limit_up_count
  3. 当日相对位置：当日强度在 N 日序列中的分位
  4. novelty 标签：is_new=True 直接进入"发酵"

输出：
  {
    "phase": "高潮",
    "phase_index": 3,            # 0-5 用于排序展示
    "score": 78,                 # 0-100 综合热度
    "appearance_days": 8,
    "trend": "上升" | "下降" | "震荡",
    "history": [{date, intensity, limit_up_count, change_rate}, ...],
    "reason": "appearance_days=8, 近5日强度持续上升，今日 limit_up_count 创近期新高",
    "advice": "高潮阶段：龙头优先，警惕分歧",
  }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PHASES = ["冷却", "中性", "发酵", "启动", "高潮", "退潮"]
PHASE_INDEX = {p: i for i, p in enumerate(PHASES)}

_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"


def _load_snapshot(date: str) -> Optional[dict]:
    p = _CACHE_DIR / f"snapshot_{date}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_sector(sector: dict) -> dict:
    """规整 sector 字段（KPL 命名差异较大）。"""
    return {
        "name": sector.get("PlateName") or sector.get("concept_name") or sector.get("name") or "",
        "intensity": float(sector.get("Intensity") or sector.get("intensity") or 0),
        "change_rate": float(sector.get("ChangePercent") or sector.get("change_rate") or 0),
        "limit_up_count": int(sector.get("LimitUpNum") or sector.get("limit_up_count") or 0),
        "main_force": float(sector.get("MainForce") or sector.get("main_force") or 0),
    }


def get_theme_history_series(theme: str, days: int = 10) -> list[dict]:
    """
    从 snapshot 文件序列里抽取指定题材的每日数据点。
    跳过周末与无快照日期。
    """
    out: list[dict] = []
    today = datetime.now()
    for i in range(days, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        snap = _load_snapshot(d)
        if not snap:
            continue
        for s in snap.get("sectors", []):
            row = _extract_sector(s)
            if theme in row["name"] or row["name"] in theme:
                out.append({"date": d, **row})
                break
    return out


def _compute_trend(series: list[float]) -> tuple[str, float]:
    """计算趋势方向 + 斜率（用线性增长率近似）。"""
    if len(series) < 2:
        return "震荡", 0.0
    # 取后半段斜率：避免远端噪声
    recent = series[-min(5, len(series)):]
    head = recent[0] if recent[0] else 1
    tail = recent[-1]
    if head == 0:
        return ("上升" if tail > 0 else "震荡"), tail
    delta_pct = (tail - head) / abs(head)
    if delta_pct >= 0.15:
        return "上升", delta_pct
    if delta_pct <= -0.15:
        return "下降", delta_pct
    return "震荡", delta_pct


def classify_theme_phase(
    theme: str,
    appearance_days: int = 0,
    today_sector: Optional[dict] = None,
    history: Optional[list[dict]] = None,
    novelty: str = "existing",
) -> dict:
    """
    五阶段判定：
      - novelty="new" 或 appearance_days <= 2 → 发酵
      - 3 ≤ days ≤ 7 + 趋势上升 + limit_up_count ≥ 3 → 启动
      - 5 ≤ days ≤ 15 + 当日强度处于序列 top + limit_up_count ≥ 5 → 高潮
      - days ≥ 7 + 趋势下降 + 当日强度跌破 60% 分位 → 退潮
      - days ≥ 15 + limit_up_count ≤ 1 + 强度低位 → 冷却
      - 其他 → 中性
    """
    history = history or []
    today = today_sector or (history[-1] if history else {})
    today_intensity = float(today.get("intensity", 0) or 0)
    today_lu = int(today.get("limit_up_count", 0) or 0)

    intensities = [h["intensity"] for h in history if h.get("intensity") is not None]
    trend, slope = _compute_trend(intensities)

    if intensities:
        sorted_int = sorted(intensities)
        rank = sum(1 for v in sorted_int if v <= today_intensity) / len(sorted_int)
    else:
        rank = 0.5

    # ---------- 阶段判定 ----------
    if novelty == "new" or appearance_days <= 2:
        phase = "发酵"
        reason = f"题材新出现（{appearance_days}日），尚未充分扩散"
        advice = "🌱 关注首板个股是否能持续，警惕一日游"
    elif appearance_days <= 7 and trend == "上升" and today_lu >= 3:
        phase = "启动"
        reason = f"出现 {appearance_days} 日，强度上升，今日涨停 {today_lu} 家"
        advice = "🚀 启动阶段：可低吸主线 1-2 板，关注题材龙头"
    elif 5 <= appearance_days <= 15 and rank >= 0.7 and today_lu >= 5:
        phase = "高潮"
        reason = f"持续 {appearance_days} 日，当日强度居 N 日 top {int((1-rank)*100)}%，涨停 {today_lu} 家"
        advice = "🔥 高潮阶段：龙头优先，警惕高位分歧"
    elif appearance_days >= 7 and trend == "下降" and rank < 0.6:
        phase = "退潮"
        reason = f"持续 {appearance_days} 日，强度下降趋势（斜率 {slope:.2f}），跌出强势区"
        advice = "💧 退潮阶段：减仓避雷，等待二波或转向新主线"
    elif appearance_days >= 15 and today_lu <= 1 and rank < 0.3:
        phase = "冷却"
        reason = f"题材已活跃 {appearance_days} 日，今日仅 {today_lu} 家涨停，强度低位"
        advice = "❄️ 冷却阶段：暂时回避，等待新催化"
    else:
        phase = "中性"
        reason = f"appearance_days={appearance_days}, 趋势{trend}, 涨停{today_lu}家，无明确信号"
        advice = "🤔 分歧阶段：观望为主"

    # 综合热度分（0-100）
    score = max(0, min(100, int(
        rank * 50 +
        min(today_lu, 10) * 4 +
        (10 if trend == "上升" else -10 if trend == "下降" else 0) +
        min(today_intensity, 100) * 0.1
    )))

    return {
        "theme": theme,
        "phase": phase,
        "phase_index": PHASE_INDEX[phase],
        "score": score,
        "appearance_days": appearance_days,
        "novelty": novelty,
        "trend": trend,
        "slope": round(slope, 3),
        "today_intensity": today_intensity,
        "today_limit_up": today_lu,
        "rank_pct": round(rank * 100, 1),
        "history": history,
        "reason": reason,
        "advice": advice,
    }


# 阶段对应的 antd 颜色 / icon（前端可直接消费）
PHASE_STYLE = {
    "发酵": {"color": "cyan", "icon": "🌱"},
    "启动": {"color": "blue", "icon": "🚀"},
    "高潮": {"color": "red", "icon": "🔥"},
    "退潮": {"color": "orange", "icon": "💧"},
    "冷却": {"color": "default", "icon": "❄️"},
    "中性": {"color": "default", "icon": "🤔"},
}
