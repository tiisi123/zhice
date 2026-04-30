from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel

from apps.api.auth import current_user
from apps.api.db import execute, query_all, query_one
from packages.connectors.registry import get_kpl
from packages.features.analysis import build_broken_case, recommend_strategy

router = APIRouter()
_kpl = get_kpl()


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@router.get("/broken-cases")
def broken_cases(date: Optional[str] = Query(None)):
    trade_date = date or datetime.now().strftime("%Y-%m-%d")
    try:
        broken = _kpl.get_broken(trade_date)
        cases = [build_broken_case(s) for s in broken] if broken else []

        by_reason: dict[str, list] = {}
        for c in cases:
            by_reason.setdefault(c["reason_type"], []).append(c)

        return {
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "total": len(cases),
            "by_reason": {k: {"count": len(v), "cases": v} for k, v in by_reason.items()},
            "mock": False,
            "source": "kpl",
            "data_status": "ok" if cases else "empty",
        }
    except Exception as e:
        return {
            "trade_date": trade_date,
            "updated_at": _now_text(),
            "total": 0,
            "by_reason": {},
            "mock": False,
            "source": "kpl",
            "data_status": "unavailable",
            "message": f"获取炸板案例失败: {str(e)}",
        }


@router.get("/strategy-recommend")
def strategy_recommend(sentiment: str = Query("中性"), max_board: int = Query(3)):
    try:
        recs = recommend_strategy(sentiment, max_board)
        return {"sentiment": sentiment, "max_board": max_board, "recommendations": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"策略推荐失败: {str(e)}")


class ReportSaveInput(BaseModel):
    trade_date: str
    report: str
    sentiment: str = ""
    limit_up: int = 0
    broken: int = 0


@router.post("/save-report")
def save_report(inp: ReportSaveInput, user: dict = Depends(current_user)):
    try:
        author_name = user.get("nickname") or "智策官方"
        summary = f"涨停{inp.limit_up} 炸板{inp.broken} 情绪{inp.sentiment}"
        report_id = execute(
            """INSERT INTO reports_archive(author_id, author_name, trade_date, kind, title, content, summary)
               VALUES (?,?,?,?,?,?,?)""",
            (
                user["id"],
                author_name,
                inp.trade_date,
                "manual",
                f"{inp.trade_date} 复盘报告",
                inp.report,
                summary,
            ),
        )
        total = query_one("SELECT COUNT(*) AS cnt FROM reports_archive") or {"cnt": 0}
        return {"message": "报告已存档", "id": report_id, "total_saved": total["cnt"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存报告失败: {str(e)}")


@router.get("/report-archive")
def report_archive(
    date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(current_user),
):
    params: list = [user["id"]]
    where = "WHERE (author_id IS NULL OR author_id=1 OR author_id=?)"
    if date:
        where += " AND trade_date=?"
        params.append(date)
    params.append(limit)
    rows = query_all(
        f"""SELECT id, author_id, author_name, trade_date, kind, title, content AS report, summary, created_at
            FROM reports_archive
            {where}
            ORDER BY trade_date DESC, id DESC
            LIMIT ?""",
        params,
    )
    for row in rows:
        text = row.get("summary") or ""
        row["sentiment"] = next((s for s in ["高潮", "回暖", "中性", "低迷", "冰点"] if s in text), "")
        limit_up_match = re.search(r"涨停(\d+)", text)
        broken_match = re.search(r"炸板(\d+)", text)
        row["limit_up"] = int(limit_up_match.group(1)) if limit_up_match else ""
        row["broken"] = int(broken_match.group(1)) if broken_match else ""
    return {"count": len(rows), "reports": rows}


@router.get("/report-authors")
def report_authors(_user: dict = Depends(current_user)):
    rows = query_all(
        "SELECT id, nickname, vip_level, style FROM users WHERE vip_level IN ('pro','vip') ORDER BY id LIMIT 50"
    )
    if not rows:
        rows = [{"id": 1, "nickname": "智策官方", "vip_level": "pro", "style": "short"}]
    return {"authors": rows}


class SubscribeInput(BaseModel):
    author_id: int
    author_name: str = ""
    enabled: bool = True


@router.get("/subscriptions")
def list_subscriptions(user: dict = Depends(current_user)):
    rows = query_all(
        """SELECT id, author_id, author_name, enabled, created_at
           FROM report_subscriptions
           WHERE user_id=?
           ORDER BY id DESC""",
        (user["id"],),
    )
    for row in rows:
        row["enabled"] = bool(row.get("enabled"))
    return {"items": rows, "total": len(rows)}


@router.post("/subscriptions")
def save_subscription(inp: SubscribeInput, user: dict = Depends(current_user)):
    name = inp.author_name.strip()
    if not name:
        author = query_one("SELECT nickname FROM users WHERE id=?", (inp.author_id,))
        name = (author or {}).get("nickname") or f"作者{inp.author_id}"
    row = query_one(
        "SELECT id FROM report_subscriptions WHERE user_id=? AND author_id=?",
        (user["id"], inp.author_id),
    )
    if row:
        execute(
            """UPDATE report_subscriptions
               SET author_name=?, enabled=?
               WHERE user_id=? AND author_id=?""",
            (name, 1 if inp.enabled else 0, user["id"], inp.author_id),
        )
    else:
        execute(
            """INSERT INTO report_subscriptions(user_id, author_id, author_name, enabled)
               VALUES (?,?,?,?)""",
            (user["id"], inp.author_id, name, 1 if inp.enabled else 0),
        )
    return {"ok": True, "author_id": inp.author_id, "author_name": name, "enabled": inp.enabled}


@router.delete("/subscriptions/{author_id}")
def delete_subscription(author_id: int, user: dict = Depends(current_user)):
    execute(
        "DELETE FROM report_subscriptions WHERE user_id=? AND author_id=?",
        (user["id"], author_id),
    )
    return {"ok": True}


@router.get("/subscription-feed")
def subscription_feed(limit: int = Query(20, ge=1, le=100), user: dict = Depends(current_user)):
    subs = query_all(
        "SELECT author_id, author_name FROM report_subscriptions WHERE user_id=? AND enabled=1",
        (user["id"],),
    )
    if not subs:
        return {"items": [], "total": 0, "subscribed_authors": []}
    rows = query_all(
        """SELECT r.id, r.author_id, r.author_name, r.trade_date, r.kind, r.title, r.summary, r.content, r.created_at
           FROM reports_archive r
           JOIN report_subscriptions s ON s.user_id=? AND s.enabled=1 AND s.author_id=COALESCE(r.author_id, 1)
           ORDER BY r.trade_date DESC, r.id DESC
           LIMIT ?""",
        (user["id"], limit),
    )
    for row in rows:
        row["author_id"] = row.get("author_id") or 1
        row["author_name"] = row.get("author_name") or "智策官方"
    return {"items": rows, "total": len(rows), "subscribed_authors": subs}
