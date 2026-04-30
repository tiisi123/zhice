"""
M3-04 AI 策略推荐
=================
评分维度（综合分 = Σ 加权）：
  1. 主风格匹配（问卷/设置）       w=1.0
  2. 副风格匹配（最近行为埋点）    w=0.4
  3. 市场情绪适配度（实时拉 summary）w=0.6
  4. 风险偏好匹配（问卷答案 risk）  w=0.3
另：每条推荐附带 AI 生成的"为什么现在适合你"短评（缓存 5 分钟）。
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from apps.api.auth import current_user
from apps.api.db import _DB_PATH
from packages.connectors.registry import get_kpl
from packages.features.market import build_market_summary

logger = logging.getLogger(__name__)
router = APIRouter()
VALID_STYLES = {"short", "hot", "growth", "value"}


def _quick_query_all(sql: str, params: tuple = ()) -> list[dict]:
    try:
        conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True, timeout=0.3)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("recommend optional query skipped: %s", e)
        return []


def _quick_query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = _quick_query_all(sql, params)
    return rows[0] if rows else None


# 策略模板库（与前端 StrategyPage 模板库保持一致）
TEMPLATES = [
    {
        "id": "first_board_seal",
        "name": "首板打板：强封单 + 题材龙头",
        "style": "short",
        "tags": ["打板", "短线"],
        "dsl": {
            "select": {"涨停类型": "首板", "题材热度": {"rank": "top5"}, "封单金额": {"gte": 50000000}},
            "entry": {"condition": "首次涨停"},
            "exit": {"止盈": 8, "止损": -4, "持有天数上限": 1},
        },
    },
    {
        "id": "tier_div_buyback",
        "name": "连板龙头首次分歧低吸",
        "style": "short",
        "tags": ["打板", "低吸"],
        "dsl": {
            "select": {"连板次数": {"gte": 3}, "龙头标签": True, "题材热度": {"rank": "top3"}},
            "entry": {"condition": "分歧转一致", "开盘涨幅": {"lte": 3}},
            "exit": {"止盈": 15, "止损": -5, "持有天数上限": 3},
        },
    },
    {
        "id": "theme_follow",
        "name": "题材轮动跟随：次日低吸",
        "style": "hot",
        "tags": ["热点", "轮动"],
        "dsl": {
            "select": {"题材热度": {"rank": "top3"}, "新题材": True},
            "entry": {"condition": "次日低开", "开盘涨幅": {"lte": 1}},
            "exit": {"止盈": 12, "止损": -6, "持有天数上限": 5},
        },
    },
    {
        "id": "industry_boom",
        "name": "景气度拐点：上修标的",
        "style": "growth",
        "tags": ["成长", "景气度"],
        "dsl": {
            "select": {"行业景气": {"gte": 0.6}, "盈利上修": True},
            "entry": {"condition": "回踩均线企稳"},
            "exit": {"止盈": 25, "止损": -10, "持有天数上限": 60},
        },
    },
    {
        "id": "value_roe",
        "name": "价值组合：低估值高 ROE",
        "style": "value",
        "tags": ["价值", "基本面"],
        "dsl": {
            "select": {"PE": {"lte": 15}, "ROE": {"gte": 12}, "分红率": {"gte": 3}},
            "entry": {"condition": "月度再平衡"},
            "exit": {"止盈": 40, "止损": -15, "持有天数上限": 180},
        },
    },
    {
        "id": "etf_rotation",
        "name": "ETF 轮动：动量 + 景气",
        "style": "growth",
        "tags": ["ETF", "轮动"],
        "dsl": {
            "select": {"动量20日": {"rank": "top3"}, "景气趋势": "向上"},
            "entry": {"condition": "月初再平衡"},
            "exit": {"止盈": 20, "止损": -8, "持有天数上限": 30},
        },
    },
    {
        "id": "broken_rescue",
        "name": "炸板后撬板：情绪回暖日",
        "style": "short",
        "tags": ["打板", "撬板"],
        "dsl": {
            "select": {"昨炸板": True, "环境情绪": {"gte": "回暖"}},
            "entry": {"condition": "次日首次涨停"},
            "exit": {"止盈": 10, "止损": -5, "持有天数上限": 2},
        },
    },
]


def _style_from_behavior(user_id: int) -> dict[str, int]:
    from collections import Counter
    rows = _quick_query_all(
        "SELECT page FROM events WHERE user_id=? ORDER BY id DESC LIMIT 200", (user_id,)
    )
    mapping = {
        "/replay": "short", "/intraday": "short", "/sentiment": "short", "/broken-cases": "short",
        "/theme": "hot", "/chain": "hot",
        "/growth": "growth", "/etf-rotation": "growth",
        "/value": "value", "/valuation": "value",
    }
    c: Counter[str] = Counter()
    for r in rows:
        p = r.get("page") or ""
        for k, v in mapping.items():
            if p.startswith(k):
                c[v] += 1
                break
    return dict(c)


@router.get("/templates")
def templates():
    return {"templates": TEMPLATES}


# ============== 市场情绪适配 ==============
# 每个 style 在不同情绪下的"亲和系数"，0.0~1.0，越高越适合
_STYLE_VS_SENTIMENT = {
    "short": {"高潮": 1.00, "回暖": 0.85, "中性": 0.45, "低迷": 0.15, "冰点": 0.05},
    "hot":   {"高潮": 0.85, "回暖": 1.00, "中性": 0.65, "低迷": 0.30, "冰点": 0.10},
    "growth": {"高潮": 0.55, "回暖": 0.70, "中性": 0.85, "低迷": 0.95, "冰点": 1.00},
    "value":  {"高潮": 0.40, "回暖": 0.55, "中性": 0.85, "低迷": 1.00, "冰点": 0.95},
}


_summary_cache: tuple[float, dict] | None = None
_SUMMARY_CACHE_TTL = 60
_SUMMARY_TIMEOUT_SEC = 3
_summary_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommend-summary")


def _neutral_summary() -> dict:
    return {"sentiment_level": "中性", "limit_up_count": 0, "max_board": 0, "broken_rate": 0}


def _fetch_market_summary_live() -> dict:
    kpl = get_kpl()
    d = datetime.now().strftime("%Y-%m-%d")
    kpl_stats = kpl.get_market_statistics(d) or []
    limit_up = kpl.get_limit_up(d) or []
    broken = kpl.get_broken(d) or []
    return build_market_summary(kpl_stats, limit_up, broken)


def _get_market_summary() -> dict:
    """实时拉今日 summary，失败或上游过慢时兜底为'中性'。"""
    global _summary_cache
    now = time.time()
    if _summary_cache and now - _summary_cache[0] < _SUMMARY_CACHE_TTL:
        return _summary_cache[1]
    try:
        future = _summary_executor.submit(_fetch_market_summary_live)
        summary = future.result(timeout=_SUMMARY_TIMEOUT_SEC)
        _summary_cache = (now, summary)
        return summary
    except FutureTimeout:
        logger.warning("recommend: get summary timed out after %ss", _SUMMARY_TIMEOUT_SEC)
        summary = _neutral_summary()
        _summary_cache = (now, summary)
        return summary
    except Exception as e:
        logger.warning("recommend: get summary failed: %s", e)
        summary = _neutral_summary()
        _summary_cache = (now, summary)
        return summary


def _primary_style(user: dict) -> str:
    style = user.get("style") or "short"
    prof = _quick_query_one("SELECT style FROM style_profile WHERE user_id=?", (user["id"],))
    if prof and prof.get("style") in VALID_STYLES:
        style = prof["style"]
    return style if style in VALID_STYLES else "short"


def _risk_from_profile(user_id: int) -> str:
    """从 style_profile.answers 中提取风险偏好：保守 / 平衡 / 进取。"""
    row = _quick_query_one("SELECT answers FROM style_profile WHERE user_id=?", (user_id,))
    if not row:
        return "平衡"
    try:
        ans = json.loads(row["answers"]) if isinstance(row["answers"], str) else row["answers"]
        # 兼容各种字段名
        risk = ans.get("risk") or ans.get("risk_pref") or ans.get("risk_level") or "平衡"
        if isinstance(risk, str):
            if "保守" in risk or "低" in risk: return "保守"
            if "进取" in risk or "高" in risk or "激进" in risk: return "进取"
        return "平衡"
    except Exception:
        return "平衡"


def _style_combo(user_id: int, fallback: str) -> list[str]:
    row = _quick_query_one("SELECT styles FROM style_combo WHERE user_id=?", (user_id,))
    if not row:
        return [fallback]
    try:
        styles = json.loads(row["styles"])
        if isinstance(styles, list):
            normalized = []
            seen: set[str] = set()
            for s in styles:
                if s in VALID_STYLES and s not in seen:
                    normalized.append(s)
                    seen.add(s)
            return normalized or [fallback]
    except Exception:
        pass
    return [fallback]


# template style -> 风险等级（保守=低波动；进取=高波动）
_TEMPLATE_RISK = {
    "first_board_seal": "进取",
    "tier_div_buyback": "进取",
    "broken_rescue": "进取",
    "theme_follow": "平衡",
    "etf_rotation": "平衡",
    "industry_boom": "平衡",
    "value_roe": "保守",
}


@router.get("/strategies")
def recommend(user: dict = Depends(current_user)):
    style = _primary_style(user)
    style_combo = _style_combo(user["id"], style)
    if style_combo:
        style = style_combo[0]
    behavior = _style_from_behavior(user["id"])
    behavior_sorted = sorted(behavior.items(), key=lambda x: -x[1])
    combo_secondary = next((s for s in style_combo[1:] if s != style), None)
    behavior_secondary = next((s for s, _ in behavior_sorted if s != style), None)
    secondary = combo_secondary or behavior_secondary
    risk_pref = _risk_from_profile(user["id"])

    # 实时市场情绪
    summary = _get_market_summary()
    sentiment = summary.get("sentiment_level", "中性")

    scored = []
    for t in TEMPLATES:
        score = 0.0
        reasons: list[str] = []
        # 1) 主风格
        if t["style"] == style:
            score += 1.0
            reasons.append(f"✓ 契合主风格「{style}」")
        # 2) 副风格
        if secondary and t["style"] == secondary:
            score += 0.4
            if combo_secondary == secondary:
                reasons.append(f"✓ 匹配组合副风格「{secondary}」")
            else:
                reasons.append(f"✓ 匹配行为副风格「{secondary}」")
        elif t["style"] in style_combo[1:]:
            score += 0.25
            reasons.append(f"✓ 匹配已开启的组合风格「{t['style']}」")
        # 3) 市场情绪适配
        affinity = _STYLE_VS_SENTIMENT.get(t["style"], {}).get(sentiment, 0.5)
        market_score = round(affinity * 0.6, 2)
        score += market_score
        if affinity >= 0.85:
            reasons.append(f"🔥 当前【{sentiment}】情绪强适配（亲和 {affinity:.0%}）")
        elif affinity >= 0.6:
            reasons.append(f"✓ 适合当前【{sentiment}】环境")
        elif affinity < 0.3:
            reasons.append(f"⚠️ 当前【{sentiment}】不利此策略（亲和仅 {affinity:.0%}）")
        # 4) 风险偏好匹配
        t_risk = _TEMPLATE_RISK.get(t["id"], "平衡")
        if t_risk == risk_pref:
            score += 0.3
            reasons.append(f"✓ 匹配风险偏好「{risk_pref}」")
        elif (risk_pref == "保守" and t_risk == "进取") or (risk_pref == "进取" and t_risk == "保守"):
            score -= 0.2
            reasons.append(f"⚠️ 与风险偏好「{risk_pref}」相悖（策略偏 {t_risk}）")
        # 5) 行为兜底
        if not behavior:
            score += 0.05

        scored.append({
            **t,
            "score": round(score, 2),
            "market_score": market_score,
            "affinity": affinity,
            "risk_level": t_risk,
            "reasons": reasons,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "primary_style": style,
        "secondary_style": secondary,
        "style_combo": style_combo,
        "risk_preference": risk_pref,
        "market_sentiment": sentiment,
        "market_summary": {
            "limit_up_count": summary.get("limit_up_count", 0),
            "max_board": summary.get("max_board", 0),
            "broken_rate": summary.get("broken_rate", 0),
        },
        "behavior_votes": behavior,
        "recommendations": scored[:6],
        "weights": {
            "main_style": 1.0,
            "secondary_style": 0.4,
            "market_adapt": 0.6,
            "risk_match": 0.3,
        },
    }


# ============== AI 推荐理由（缓存 5 分钟） ==============
_explain_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 300
_EXPLAIN_TIMEOUT_SEC = 6
_explain_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="recommend-explain")


@router.get("/explain/{template_id}")
def explain(template_id: str, user: dict = Depends(current_user)):
    """让 AI 为指定模板生成"为什么现在适合你"的短评（150-250 字）。"""
    cache_key = f"{user['id']}:{template_id}"
    now = time.time()
    cached = _explain_cache.get(cache_key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    template = next((t for t in TEMPLATES if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 拼接上下文
    style = _primary_style(user)
    combo = _style_combo(user["id"], style)
    if combo:
        style = combo[0]
    summary = _get_market_summary()
    risk = _risk_from_profile(user["id"])

    from apps.ai.agents.llm_client import llm

    prompt = f"""你是一名资深 A 股策略分析师，请用 150-250 字向用户解释【为什么现在适合采用这个策略】。

【用户画像】
- 主风格：{style}
- 开启风格：{", ".join(combo)}
- 风险偏好：{risk}

【策略模板】
- 名称：{template['name']}
- 风格：{template['style']}
- 选股条件：{json.dumps(template['dsl'].get('select', {}), ensure_ascii=False)}
- 进出场：{json.dumps({'entry': template['dsl'].get('entry'), 'exit': template['dsl'].get('exit')}, ensure_ascii=False)}

【今日市场】
- 情绪：{summary.get('sentiment_level', '中性')}
- 涨停 {summary.get('limit_up_count', 0)} 家，最高 {summary.get('max_board', 0)} 板
- 炸板率 {summary.get('broken_rate', 0):.1f}%

请输出 Markdown，包含：
1. **当下适配性**（市场环境是否利好该策略）
2. **关键风险**（一句话）
3. **执行要点**（仓位/止损/触发信号）

语气精炼专业，不要套话。"""
    try:
        future = _explain_executor.submit(llm.chat, prompt)
        text = future.result(timeout=_EXPLAIN_TIMEOUT_SEC)
    except FutureTimeout:
        logger.warning("recommend explain timed out after %ss", _EXPLAIN_TIMEOUT_SEC)
        text = "AI 解读暂时繁忙，请稍后重试。策略推荐列表不受影响。"
    except Exception as e:
        logger.exception("explain LLM failed")
        text = f"AI 解读暂不可用：{e}"

    result = {
        "template_id": template_id,
        "name": template["name"],
        "explanation": text,
        "market_sentiment": summary.get("sentiment_level"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "disclaimer": "AI 生成，不构成投资建议。",
    }
    _explain_cache[cache_key] = (now, result)
    return result
