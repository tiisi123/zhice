"""M1-08 自定义看板：保存/加载用户拖拽布局。"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.auth import current_user
from apps.api.db import execute, query_one, query_all

router = APIRouter()


WIDGET_CATALOG = [
    {"key": "market_summary", "name": "今日行情总览", "tags": ["短线", "必备"]},
    {"key": "ladder", "name": "连板天梯", "tags": ["短线"]},
    {"key": "sentiment_gauge", "name": "市场情绪仪表盘", "tags": ["短线"]},
    {"key": "theme_hot", "name": "题材热度排行", "tags": ["短线", "热点"]},
    {"key": "sector_rank", "name": "板块涨跌排行", "tags": ["通用"]},
    {"key": "capital_flow", "name": "资金流向", "tags": ["通用"]},
    {"key": "limit_up_table", "name": "涨停实时扫描", "tags": ["盘中"]},
    {"key": "broken_cases", "name": "炸板追踪", "tags": ["盘中"]},
    {"key": "alerts", "name": "异动流", "tags": ["盘中"]},
    {"key": "etf_rotation", "name": "ETF 轮动", "tags": ["成长"]},
    {"key": "growth_heatmap", "name": "景气度热力图", "tags": ["成长"]},
    {"key": "valuation_scatter", "name": "估值分位散点", "tags": ["价值"]},
    {"key": "portfolio", "name": "持仓仪表盘", "tags": ["价值"]},
    {"key": "longhu", "name": "龙虎榜席位", "tags": ["短线"]},
    {"key": "ai_summary", "name": "AI 摘要卡", "tags": ["通用"]},
]


class SaveBoardIn(BaseModel):
    id: int | None = None
    name: str
    layout: list[dict[str, Any]]
    is_default: bool = False


@router.get("/widgets")
def widgets():
    return {"widgets": WIDGET_CATALOG}


@router.get("/list")
def list_boards(user: dict = Depends(current_user)):
    rows = query_all(
        "SELECT id, name, is_default, updated_at FROM dashboards WHERE user_id=? ORDER BY is_default DESC, id DESC",
        (user["id"],),
    )
    return {"boards": rows}


@router.get("/{board_id}")
def get_board(board_id: int, user: dict = Depends(current_user)):
    row = query_one(
        "SELECT * FROM dashboards WHERE id=? AND user_id=?", (board_id, user["id"])
    )
    if not row:
        raise HTTPException(status_code=404, detail="看板不存在")
    try:
        row["layout"] = json.loads(row["layout"])
    except Exception:
        row["layout"] = []
    return row


@router.post("/save")
def save_board(inp: SaveBoardIn, user: dict = Depends(current_user)):
    layout_json = json.dumps(inp.layout[:20], ensure_ascii=False)
    if inp.is_default:
        execute("UPDATE dashboards SET is_default=0 WHERE user_id=?", (user["id"],))
    if inp.id:
        row = query_one(
            "SELECT id FROM dashboards WHERE id=? AND user_id=?", (inp.id, user["id"])
        )
        if not row:
            raise HTTPException(status_code=404, detail="看板不存在")
        execute(
            "UPDATE dashboards SET name=?, layout=?, is_default=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (inp.name, layout_json, 1 if inp.is_default else 0, inp.id),
        )
        return {"id": inp.id, "ok": True}
    new_id = execute(
        "INSERT INTO dashboards(user_id, name, layout, is_default) VALUES (?,?,?,?)",
        (user["id"], inp.name, layout_json, 1 if inp.is_default else 0),
    )
    return {"id": new_id, "ok": True}


@router.delete("/{board_id}")
def delete_board(board_id: int, user: dict = Depends(current_user)):
    execute("DELETE FROM dashboards WHERE id=? AND user_id=?", (board_id, user["id"]))
    return {"ok": True}
