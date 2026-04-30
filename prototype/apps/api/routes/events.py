from __future__ import annotations

import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.api.auth import optional_user, current_user
from apps.api.db import execute, query_all

router = APIRouter()


class EventIn(BaseModel):
    event: str
    page: str | None = None
    props: dict | None = None


@router.post("/track")
def track(inp: EventIn, user: dict | None = Depends(optional_user)):
    execute(
        "INSERT INTO events(user_id, event, page, props) VALUES (?,?,?,?)",
        (
            user["id"] if user else None,
            inp.event[:64],
            (inp.page or "")[:128],
            json.dumps(inp.props or {}, ensure_ascii=False)[:2000],
        ),
    )
    return {"ok": True}


@router.get("/mine")
def mine(limit: int = 50, user: dict = Depends(current_user)):
    rows = query_all(
        "SELECT event, page, props, created_at FROM events WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user["id"], max(1, min(limit, 200))),
    )
    return {"events": rows}


@router.get("/stats")
def stats(days: int = 7, user: dict = Depends(current_user)):
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    rows = query_all(
        "SELECT event, COUNT(*) AS cnt FROM events WHERE user_id=? AND created_at >= ? GROUP BY event ORDER BY cnt DESC",
        (user["id"], since),
    )
    return {"since": since, "stats": rows}
