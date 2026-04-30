"""M4B-10 新题材识别：基于历史出现记录标注「首次出现 / 重新激活」。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from apps.api.db import execute, query_one, query_all


def mark_themes(themes: list[dict[str, Any]], trade_date: str | None = None) -> list[dict[str, Any]]:
    """给每个 theme dict 打上 novelty 标签。
    字段要求：至少包含 name（或 id -> name）。
    """
    today = trade_date or datetime.now().strftime("%Y-%m-%d")
    enriched: list[dict] = []
    for t in themes:
        name = t.get("name") or t.get("PlateName") or t.get("id")
        if not name:
            enriched.append(t)
            continue
        row = query_one("SELECT * FROM theme_history WHERE theme_name=?", (name,))
        novelty = "existing"
        first_seen = today
        if not row:
            novelty = "new"
            execute(
                "INSERT OR IGNORE INTO theme_history(theme_name, first_seen, last_seen, appearance_days) VALUES (?,?,?,1)",
                (name, today, today),
            )
        else:
            first_seen = row["first_seen"]
            try:
                gap = (
                    datetime.strptime(today, "%Y-%m-%d")
                    - datetime.strptime(row["last_seen"], "%Y-%m-%d")
                ).days
            except Exception:
                gap = 0
            if gap >= 15:
                novelty = "revived"
            execute(
                "UPDATE theme_history SET last_seen=?, appearance_days=appearance_days+1 WHERE theme_name=?",
                (today, name),
            )
        enriched.append({
            **t,
            "novelty": novelty,
            "first_seen": first_seen,
        })
    return enriched


def list_recent_new(days: int = 3) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return query_all(
        "SELECT theme_name, first_seen, last_seen, appearance_days FROM theme_history WHERE first_seen >= ? ORDER BY first_seen DESC",
        (since,),
    )
