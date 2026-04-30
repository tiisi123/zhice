"""M4E-01 风格测试问卷 + M4E-02 风格切换 + M4E-03 风格智能识别。"""
from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.auth import current_user, update_style
from apps.api.db import execute, query_one, query_all

router = APIRouter()


QUESTIONS = [
    {
        "id": "q1",
        "text": "你更关注哪种类型的机会？",
        "options": [
            {"value": "short", "label": "涨停板、连板龙头、打板套利"},
            {"value": "hot", "label": "热点题材、事件驱动、板块轮动"},
            {"value": "growth", "label": "高景气度行业、成长赛道"},
            {"value": "value", "label": "低估值、稳定分红、基本面扎实"},
        ],
    },
    {
        "id": "q2",
        "text": "你的预期持仓周期？",
        "options": [
            {"value": "short", "label": "1-3 天"},
            {"value": "hot", "label": "3-15 天"},
            {"value": "growth", "label": "1-3 个月"},
            {"value": "value", "label": "3 个月以上"},
        ],
    },
    {
        "id": "q3",
        "text": "你能接受的单次最大回撤？",
        "options": [
            {"value": "short", "label": "5% 以内（快进快出）"},
            {"value": "hot", "label": "10% 左右"},
            {"value": "growth", "label": "15-20%"},
            {"value": "value", "label": "20% 以上也能持有"},
        ],
    },
    {
        "id": "q4",
        "text": "你最看重哪类信号？",
        "options": [
            {"value": "short", "label": "封单、首次涨停、分歧转一致"},
            {"value": "hot", "label": "新闻催化、题材发酵节奏"},
            {"value": "growth", "label": "行业景气、订单/产能/价格"},
            {"value": "value", "label": "PE/PB/ROE/分红/现金流"},
        ],
    },
    {
        "id": "q5",
        "text": "你更依赖哪种研究方式？",
        "options": [
            {"value": "short", "label": "盘口、龙虎榜、资金异动"},
            {"value": "hot", "label": "新闻、公告、产业链传导"},
            {"value": "growth", "label": "研报、行业数据、景气拐点"},
            {"value": "value", "label": "财报、估值模型、长期逻辑"},
        ],
    },
]


class SubmitIn(BaseModel):
    answers: dict[str, str]


@router.get("/questions")
def questions():
    return {"questions": QUESTIONS}


def _infer_style(answers: dict[str, str]) -> str:
    votes = Counter(answers.values())
    if not votes:
        return "short"
    return votes.most_common(1)[0][0]


@router.post("/submit")
def submit(inp: SubmitIn, user: dict = Depends(current_user)):
    style = _infer_style(inp.answers)
    row = query_one("SELECT user_id FROM style_profile WHERE user_id=?", (user["id"],))
    payload = json.dumps(inp.answers, ensure_ascii=False)
    if row:
        execute(
            "UPDATE style_profile SET answers=?, style=?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (payload, style, user["id"]),
        )
    else:
        execute(
            "INSERT INTO style_profile(user_id, answers, style) VALUES (?,?,?)",
            (user["id"], payload, style),
        )
    update_style(user["id"], style)
    return {"style": style, "answers": inp.answers}


@router.get("/profile")
def profile(user: dict = Depends(current_user)):
    row = query_one("SELECT * FROM style_profile WHERE user_id=?", (user["id"],))
    if not row:
        return {"style": user["style"], "has_profile": False}
    try:
        answers = json.loads(row["answers"])
    except Exception:
        answers = {}
    return {
        "style": row["style"],
        "has_profile": True,
        "answers": answers,
        "updated_at": row["updated_at"],
    }


@router.get("/detect")
def detect_from_behavior(user: dict = Depends(current_user)):
    """M4E-03：基于最近埋点行为推断风格倾向。"""
    rows = query_all(
        "SELECT page, event FROM events WHERE user_id=? ORDER BY id DESC LIMIT 300",
        (user["id"],),
    )
    mapping = {
        "/replay": "short",
        "/intraday": "short",
        "/sentiment": "short",
        "/broken-cases": "short",
        "/theme": "hot",
        "/chain": "hot",
        "/growth": "growth",
        "/etf-rotation": "growth",
        "/value": "value",
        "/valuation": "value",
    }
    votes: Counter[str] = Counter()
    for r in rows:
        p = r.get("page") or ""
        for k, v in mapping.items():
            if p.startswith(k):
                votes[v] += 1
                break
    if not votes:
        return {"detected": user["style"], "votes": {}, "sample": 0}
    top = votes.most_common(1)[0][0]
    return {"detected": top, "votes": dict(votes), "sample": len(rows)}
