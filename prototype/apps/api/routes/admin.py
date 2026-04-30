"""M001/S03/T04 业主后台 admin 路由 —— Cookie 录入 / 健康面板 / 告警 ack。

所有端点都通过 :func:`apps.api.auth.require_admin` 守门（``vip_level=='pro'``
AND ``phone=='admin'``），与 payment.py 的邀请码端点共享同一把锁。前端 admin
shell（S04）会在拿到 ``current_user`` 之后才渲染入口；这里再做一道服务端
校验防止前端被绕过。

端点摘要
--------
``GET  /api/admin/kpl-cookie``           Cookie 元数据（``has_cookie`` /
                                         ``last_updated_at`` / ``last_ok_*``），
                                         **永不**返回明文/密文。
``POST /api/admin/kpl-cookie``           录入 Cookie；走
                                         :func:`cookie_provider.set_kpl_cookie`，
                                         可选触发一次 KPL 健康探测。
``GET  /api/admin/health/kpl``           读 T05 _HEALTH_CACHE，T05 未上线时
                                         降级返回 ``{realtime, history: 'unknown'}``。
``POST /api/admin/health/kpl/trigger``   手动触发探测（同样 T05 未上线时无操作返回）。
``GET  /api/admin/alerts``               告警表分页（kind / unresolved 过滤）。
``POST /api/admin/alerts/{id}/ack``      ack 单条告警（``resolved_at = NOW()``）。

T05 依赖
--------
``trigger_health_probe_now`` / ``get_health_cache`` 在 T05 落地。当前导入用
``ImportError`` 兜底，让 T04 端点在 T05 之前也可单独验证。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from apps.api.auth import current_user, require_admin
from apps.api.db import execute, query_all, query_one
from apps.api.services import cookie_provider

logger = logging.getLogger("zhice.api.routes.admin")
router = APIRouter()


class CookieIn(BaseModel):
    """Pydantic 入参 —— Cookie 长度强约束防超长 / 空字符串绕过。"""

    cookie: str = Field(min_length=1, max_length=4096)
    secret_type: str = "cookie"


class AckOk(BaseModel):
    success: bool = True


# ---------------------------------------------------------------------------
# /kpl-cookie  —— Cookie 录入与元数据
# ---------------------------------------------------------------------------


@router.get("/kpl-cookie")
def get_kpl_cookie_metadata(user: dict = Depends(current_user)) -> dict:
    """业主后台 KPL Cookie 元数据。

    返回 ``has_cookie`` / ``last_updated_at`` / ``updated_by`` /
    ``last_ok_realtime`` / ``last_ok_history``。**永不**返回 ``secret_value``
    明文 —— ``cookie_provider.get_kpl_cookie_metadata()`` 自身已经做掉这条
    redaction，路由层再不去碰密文一眼。

    T05 ``_HEALTH_CACHE`` 未就绪时 ``last_ok_*`` 字段为 ``None``，前端
    HealthLight 据此显示 ``unknown`` 灰色。
    """
    require_admin(user)
    meta = cookie_provider.get_kpl_cookie_metadata()
    try:
        from apps.api.services.kpl_health import get_health_cache  # type: ignore
        cache = get_health_cache() or {}
        meta["last_ok_realtime"] = (cache.get("realtime") or {}).get("last_ok_at")
        meta["last_ok_history"] = (cache.get("history") or {}).get("last_ok_at")
    except ImportError:
        meta["last_ok_realtime"] = None
        meta["last_ok_history"] = None
    logger.info(
        "admin GET /kpl-cookie user_id=%s has_cookie=%s",
        user.get("id"),
        meta.get("has_cookie"),
    )
    return meta


@router.post("/kpl-cookie")
def set_kpl_cookie(inp: CookieIn, user: dict = Depends(current_user)) -> dict:
    """业主录入 Cookie。

    走 :func:`cookie_provider.set_kpl_cookie` —— 加密 + UPDATE +
    缓存失效一气呵成。可选触发一次 T05 健康探测；T05 未就绪时静默继续，
    业主下次 30min 周期会自然探到。
    """
    require_admin(user)
    cookie_provider.set_kpl_cookie(inp.cookie, updated_by=user.get("id"))
    logger.info(
        "admin POST /kpl-cookie user_id=%s len=%d",
        user.get("id"),
        len(inp.cookie),
    )
    triggered = False
    try:
        from apps.api.services.kpl_health import trigger_health_probe_now  # type: ignore
        trigger_health_probe_now("all")
        triggered = True
    except ImportError:
        pass
    return {
        "success": True,
        "probe_triggered": triggered,
        "message": (
            "已保存。健康探测将在下次 cron 周期触发。"
            if not triggered
            else "已保存并触发本轮 KPL 健康探测。"
        ),
    }


# ---------------------------------------------------------------------------
# /health/kpl  —— 健康面板状态
# ---------------------------------------------------------------------------


@router.get("/health/kpl")
def get_kpl_health(user: dict = Depends(current_user)) -> dict:
    """读 T05 ``_HEALTH_CACHE``。T05 未上线时返回 unknown 兜底，前端不崩。"""
    require_admin(user)
    try:
        from apps.api.services.kpl_health import get_health_cache  # type: ignore
        cache = get_health_cache() or {}
        return {
            "realtime": cache.get("realtime") or {"status": "unknown"},
            "history": cache.get("history") or {"status": "unknown"},
        }
    except ImportError:
        return {
            "realtime": {"status": "unknown"},
            "history": {"status": "unknown"},
        }


@router.post("/health/kpl/trigger")
def trigger_kpl_health(user: dict = Depends(current_user)) -> dict:
    """业主手动触发 KPL 双端点健康探测。"""
    require_admin(user)
    try:
        from apps.api.services.kpl_health import trigger_health_probe_now  # type: ignore
        trigger_health_probe_now("all")
        logger.info("admin POST /health/kpl/trigger user_id=%s triggered=True", user.get("id"))
        return {"success": True, "triggered": True}
    except ImportError:
        logger.info(
            "admin POST /health/kpl/trigger user_id=%s triggered=False (T05 not ready)",
            user.get("id"),
        )
        return {"success": True, "triggered": False, "reason": "kpl_health_module_unavailable"}


# ---------------------------------------------------------------------------
# /alerts  —— 告警列表 + ack
# ---------------------------------------------------------------------------


@router.get("/alerts")
def list_alerts(
    user: dict = Depends(current_user),
    kind: Optional[str] = Query(None, max_length=64),
    unresolved: int = Query(0, ge=0, le=1),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """``system_alerts`` 列表 + 过滤。``unresolved=1`` 只看未 ack 行。"""
    require_admin(user)
    sql = (
        "SELECT id, kind, level, message, meta, resolved_at, created_at "
        "FROM system_alerts WHERE 1=1"
    )
    params: list = []
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    if unresolved:
        sql += " AND resolved_at IS NULL"
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    try:
        rows = query_all(sql, tuple(params))
    except Exception:
        # T03 加表，但 alembic 还没跑的环境下读会 5xx。给前端一个空列表
        # 比 5xx 更友好；正确性由 /api/admin/health/kpl 反映 DB 状态。
        logger.exception("admin GET /alerts query failed")
        rows = []
    return {"alerts": rows, "count": len(rows)}


@router.post("/alerts/{alert_id}/ack")
def ack_alert(
    alert_id: int = Path(..., ge=1),
    user: dict = Depends(current_user),
) -> dict:
    """ack 单条告警 —— ``resolved_at = CURRENT_TIMESTAMP``。"""
    require_admin(user)
    row = query_one("SELECT id FROM system_alerts WHERE id = ?", (alert_id,))
    if not row:
        raise HTTPException(status_code=404, detail="告警不存在")
    execute(
        "UPDATE system_alerts SET resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (alert_id,),
    )
    logger.info("admin POST /alerts/%d/ack user_id=%s", alert_id, user.get("id"))
    return {"success": True, "alert_id": alert_id}
