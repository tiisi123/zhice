"""
研究池（自选）+ 价格异动提醒
PRD RE-004：用户研究池管理（增删改查、分组、备注）
PRD US-004：价格异动提醒（涨跌幅阈值 / 涨停 / 炸板）

数据存储：SQLite watchlist 表（见 apps/api/db.py）
权限：登录用户级隔离
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from apps.api.auth.deps import current_user
from apps.api.db import execute, query_all, query_one
from packages.connectors.registry import get_kpl

router = APIRouter()
_kpl = get_kpl()


# ============== Schemas ==============
class WatchItemIn(BaseModel):
    code: str = Field(..., description="股票代码 6 位")
    name: str = ""
    group_name: str = "默认"
    note: str = ""
    alert_change_up: Optional[float] = None      # 涨幅 % 触发
    alert_change_down: Optional[float] = None    # 跌幅 % 触发（正数，内部转为负值匹配）
    alert_limit_up: bool = True
    alert_broken: bool = True
    cost_price: Optional[float] = None
    shares: Optional[int] = None


class WatchPatch(BaseModel):
    name: Optional[str] = None
    group_name: Optional[str] = None
    note: Optional[str] = None
    alert_change_up: Optional[float] = None
    alert_change_down: Optional[float] = None
    alert_limit_up: Optional[bool] = None
    alert_broken: Optional[bool] = None
    cost_price: Optional[float] = None
    shares: Optional[int] = None


# ============== CRUD ==============
@router.get("")
def list_watch(
    group: Optional[str] = Query(None),
    user: dict = Depends(current_user),
):
    """列出当前用户的研究池。"""
    if group:
        rows = query_all(
            "SELECT * FROM watchlist WHERE user_id=? AND group_name=? ORDER BY id DESC",
            (user["id"], group),
        )
    else:
        rows = query_all(
            "SELECT * FROM watchlist WHERE user_id=? ORDER BY group_name, id DESC",
            (user["id"],),
        )
    # 字段标准化：bool
    for r in rows:
        r["alert_limit_up"] = bool(r.get("alert_limit_up"))
        r["alert_broken"] = bool(r.get("alert_broken"))
    # 同时返回分组列表
    groups = sorted({r["group_name"] for r in rows})
    return {"items": rows, "total": len(rows), "groups": groups}


@router.post("")
def add_watch(item: WatchItemIn, user: dict = Depends(current_user)):
    code = item.code.strip()
    if not code:
        raise HTTPException(status_code=400, detail="code 不能为空")
    exist = query_one(
        "SELECT id FROM watchlist WHERE user_id=? AND code=?",
        (user["id"], code),
    )
    if exist:
        raise HTTPException(status_code=409, detail="该股票已在研究池中")
    new_id = execute(
        """INSERT INTO watchlist
           (user_id, code, name, group_name, note,
            alert_change_up, alert_change_down, alert_limit_up, alert_broken,
            cost_price, shares)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user["id"], code, item.name, item.group_name or "默认", item.note,
            item.alert_change_up, item.alert_change_down,
            1 if item.alert_limit_up else 0,
            1 if item.alert_broken else 0,
            item.cost_price, item.shares,
        ),
    )
    return {"ok": True, "id": new_id}


@router.patch("/{wid}")
def patch_watch(wid: int, patch: WatchPatch, user: dict = Depends(current_user)):
    row = query_one("SELECT id FROM watchlist WHERE id=? AND user_id=?", (wid, user["id"]))
    if not row:
        raise HTTPException(status_code=404, detail="不存在")
    fields = []
    values: list = []
    for k, v in patch.model_dump(exclude_unset=True).items():
        if k in ("alert_limit_up", "alert_broken"):
            fields.append(f"{k}=?")
            values.append(1 if v else 0)
        else:
            fields.append(f"{k}=?")
            values.append(v)
    if not fields:
        return {"ok": True, "updated": 0}
    values.extend([wid, user["id"]])
    execute(f"UPDATE watchlist SET {', '.join(fields)} WHERE id=? AND user_id=?", values)
    return {"ok": True, "updated": len(fields)}


@router.delete("/{wid}")
def delete_watch(wid: int, user: dict = Depends(current_user)):
    execute("DELETE FROM watchlist WHERE id=? AND user_id=?", (wid, user["id"]))
    return {"ok": True}


# ============== 异动评估 ==============
# ============== 共用扫描函数（路由 + 调度器复用） ==============
def compute_alerts_for_user(user_id: int) -> list[dict]:
    """计算指定用户研究池当前命中的异动（实时）。"""
    rows = query_all("SELECT * FROM watchlist WHERE user_id=?", (user_id,))
    if not rows:
        return []
    trade_date = datetime.now().strftime("%Y-%m-%d")
    try:
        limit_up = _kpl.get_limit_up(trade_date) or []
        broken = _kpl.get_broken(trade_date) or []
        hot = _kpl.get_hot_stocks(trade_date) or []
    except Exception:
        limit_up, broken, hot = [], [], []

    by_code: dict[str, dict] = {}
    for s in limit_up:
        c = str(s.get("stock_code") or s.get("code") or "")
        if c:
            by_code[c] = {**s, "_status": "limit_up"}
    for s in broken:
        c = str(s.get("stock_code") or s.get("code") or "")
        if c and c not in by_code:
            by_code[c] = {**s, "_status": "broken"}
    for s in hot:
        c = str(s.get("stock_code") or s.get("code") or "")
        if c and c not in by_code:
            by_code[c] = {**s, "_status": "hot"}

    alerts: list[dict] = []
    for r in rows:
        code = r["code"]
        live = by_code.get(code)
        change = float(live.get("change_rate") or 0) if live else 0
        triggers: list[tuple[str, str]] = []
        if r.get("alert_limit_up") and live and live.get("_status") == "limit_up":
            triggers.append(("limit_up", f"{r['name'] or code} 今日涨停"))
        if r.get("alert_broken") and live and live.get("_status") == "broken":
            triggers.append(("broken", f"{r['name'] or code} 触发炸板"))
        up = r.get("alert_change_up")
        if up is not None and change >= float(up):
            triggers.append(("up", f"{r['name'] or code} 涨幅 {change:.2f}% ≥ {up}%"))
        down = r.get("alert_change_down")
        if down is not None and change <= -abs(float(down)):
            triggers.append(("down", f"{r['name'] or code} 跌幅 {abs(change):.2f}% ≥ {abs(float(down))}%"))
        for kind, msg in triggers:
            alerts.append({
                "watch_id": r["id"],
                "code": code,
                "name": r.get("name") or code,
                "group": r.get("group_name", ""),
                "kind": kind,
                "message": msg,
                "change_rate": change,
                "trade_date": trade_date,
                "ts": datetime.now().strftime("%H:%M:%S"),
            })
    return alerts


@router.get("/check-alerts")
def check_alerts(user: dict = Depends(current_user)):
    """实时扫描 + 合并当日已持久化的命中（调度器写入），统一返回。"""
    live = compute_alerts_for_user(user["id"])
    trade_date = datetime.now().strftime("%Y-%m-%d")
    persisted = query_all(
        """SELECT code, name, kind, message, change_rate, trade_date,
                  strftime('%H:%M:%S', created_at) AS ts
           FROM watch_alerts
           WHERE user_id=? AND trade_date=?
           ORDER BY id DESC""",
        (user["id"], trade_date),
    )
    # 用 (code,kind) 去重，实时优先
    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []
    for a in live + persisted:
        key = (a["code"], a["kind"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(a)
    return {"alerts": merged, "checked": len(live), "persisted": len(persisted), "trade_date": trade_date}


@router.get("/alerts/history")
def alerts_history(days: int = Query(7, ge=1, le=30), user: dict = Depends(current_user)):
    """近 N 天命中历史（来源：调度器持久化）。"""
    rows = query_all(
        """SELECT code, name, kind, message, change_rate, trade_date,
                  strftime('%H:%M:%S', created_at) AS ts
           FROM watch_alerts
           WHERE user_id=? AND date(created_at) >= date('now', ?)
           ORDER BY created_at DESC LIMIT 500""",
        (user["id"], f"-{days} days"),
    )
    return {"items": rows, "total": len(rows)}
