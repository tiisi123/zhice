"""KPL 健康探测服务（M001/S03/T05）.

两个 30 分钟探测函数（``probe_realtime`` / ``probe_history``）由
``apps.api.scheduler`` 注册成 APScheduler ``IntervalTrigger`` 任务。

Each probe 流程：
  1. 调用 T02 拆分后的 realtime/history client 的 ``*_lite`` 轻量端点；
  2. 通过 sentinel pattern（MEM046）区分四种失败：
        - ``cookie_missing`` —— cookie 缺失，不计入 ``consecutive_fail``
          （已知失败态，避免日告警风暴）；
        - ``kpl_upstream_error`` —— 上游 4xx/5xx；
        - ``malformed response`` —— 200 但 JSON 缺关键 key；
        - ``Exception`` —— 网络 / 解码异常；
  3. 在 ``_HEALTH_CACHE`` 内存 dict 里写最新状态（``GET /api/health/kpl`` 消费）；
  4. 失败路径走 ``_persist_alert`` —— 一个 ``kind`` 同时只允许一行未 resolved
     的 ``system_alerts``，已存在则 UPDATE meta + 累加 ``retry_count`` 而不是
     INSERT 新行（防止每 30 分钟一行的写抖）；
  5. 仅在 INSERT（新告警）时调用 ``_send_alert_email`` 通过 ``notify.smtp``
     发 Chinese cookie-failure 邮件给业主；
  6. 探测成功则调用 ``_resolve_alert`` 把同 kind 未 resolved 的行 ``UPDATE
     resolved_at=NOW()``，admin 面板自动转绿；上一次内存状态为 fail 时再发
     一封 ``cookie_recovery_email_body`` 让业主关闭红色警觉。

观测面：
  - 内存：``GET /api/health/kpl`` 返回 ``_HEALTH_CACHE`` 的拷贝；
  - 持久：``SELECT * FROM system_alerts ORDER BY created_at DESC`` 看历史；
  - 日志：APScheduler logger + 本模块 ``logger.exception`` 失败路径。
"""
from __future__ import annotations

import datetime
import json
import logging
import threading
from typing import Any

from apps.api.db import execute, query_one
from packages.connectors.registry import get_kpl_history, get_kpl_realtime

logger = logging.getLogger(__name__)


_INITIAL_STATE: dict[str, Any] = {
    "status": "unknown",
    "last_ok_at": None,
    "last_error": None,
    "consecutive_fail": 0,
}

_HEALTH_CACHE: dict[str, dict[str, Any]] = {
    "realtime": dict(_INITIAL_STATE),
    "history": dict(_INITIAL_STATE),
}
_CACHE_LOCK = threading.Lock()


def _is_cookie_missing(resp: Any) -> bool:
    return isinstance(resp, dict) and resp.get("_error") == "cookie_missing"


def _is_upstream_error(resp: Any) -> bool:
    return isinstance(resp, dict) and resp.get("_error") == "kpl_upstream_error"


def _now_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _persist_alert(kind: str, level: str, message: str, meta: dict) -> bool:
    """Upsert a single unresolved ``system_alerts`` row per ``kind``.

    Returns ``True`` when a brand-new row was inserted (caller should send the
    email), ``False`` when an existing unresolved row was updated (debounce —
    suppress the duplicate email). DB exceptions are caught and logged so the
    cron job survives the next tick instead of dying on a transient SQL error.
    """
    try:
        row = query_one(
            "SELECT id, meta FROM system_alerts "
            "WHERE kind=? AND resolved_at IS NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (kind,),
        )
        if row:
            try:
                existing_meta = json.loads(row.get("meta") or "{}")
            except Exception:
                existing_meta = {}
            existing_meta["retry_count"] = int(existing_meta.get("retry_count", 1)) + 1
            existing_meta.update(meta)
            execute(
                "UPDATE system_alerts SET message=?, meta=?, level=? WHERE id=?",
                (
                    message[:500],
                    json.dumps(existing_meta, ensure_ascii=False),
                    level,
                    row["id"],
                ),
            )
            return False
        execute(
            "INSERT INTO system_alerts(kind, level, message, meta) VALUES (?,?,?,?)",
            (kind, level, message[:500], json.dumps(meta, ensure_ascii=False)),
        )
        return True
    except Exception:
        logger.exception("system_alerts persist failed kind=%s", kind)
        return False


def _resolve_alert(kind: str) -> None:
    """Mark every unresolved ``system_alerts`` row of this kind as resolved."""
    try:
        execute(
            "UPDATE system_alerts SET resolved_at=CURRENT_TIMESTAMP "
            "WHERE kind=? AND resolved_at IS NULL",
            (kind,),
        )
        logger.info("alert kind=%s auto-resolved on probe success", kind)
    except Exception:
        logger.exception("auto-resolve failed kind=%s", kind)


def _extract_http_code(last_error: str | None) -> int | None:
    """Pull the HTTP code out of an ``upstream_error`` last_error string.

    ``_evaluate`` formats upstream errors as ``"kpl_upstream_error http_code=NNN"``
    so the email template can show the operator the exact status code. For
    every other failure mode (cookie_missing, malformed, network exception)
    there is no HTTP code, so we return ``None``.
    """
    if not last_error or "http_code=" not in last_error:
        return None
    try:
        return int(last_error.split("http_code=", 1)[1].strip())
    except (ValueError, IndexError):
        return None


def _send_alert_email(
    kind: str, endpoint: str, last_ok_at: str | None, last_error: str | None
) -> None:
    """Send the Chinese cookie-failure email through ``notify.smtp``."""
    from apps.api.notify.smtp import send_alert
    from apps.api.notify.templates import cookie_failure_email_body

    try:
        http_code = _extract_http_code(last_error)
        body = cookie_failure_email_body(
            endpoint, http_code, last_ok_at, last_error or "unknown"
        )
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        send_alert(f"【智策】KPL {endpoint} 健康探测失败 - {ts}", body)
    except Exception:
        logger.exception("SMTP send_alert failed kind=%s", kind)


def _send_recovery_email(kind: str, endpoint: str) -> None:
    """Send the Chinese cookie-recovery email when a failing probe turns green."""
    from apps.api.notify.smtp import send_alert
    from apps.api.notify.templates import cookie_recovery_email_body

    try:
        send_alert(
            f"【智策】KPL {endpoint} 已恢复",
            cookie_recovery_email_body(endpoint),
        )
    except Exception:
        logger.exception("SMTP send recovery failed kind=%s", kind)


def _evaluate(resp: Any, prev: dict[str, Any], list_key: str) -> dict[str, Any]:
    """Map a probe response to a fresh state dict.

    ``cookie_missing`` deliberately does **not** increment ``consecutive_fail``
    —— it is a known operator-actionable state that should surface ONCE and
    stay quiet until resolved (avoids hourly alert email spam).
    """
    prev_consec = int(prev.get("consecutive_fail", 0))
    prev_last_ok = prev.get("last_ok_at")

    if _is_cookie_missing(resp):
        return {
            "status": "fail",
            "last_ok_at": prev_last_ok,
            "last_error": "cookie_missing",
            "consecutive_fail": prev_consec,  # cookie 缺失不递增
        }
    if _is_upstream_error(resp):
        http_code = resp.get("http_code")
        return {
            "status": "fail",
            "last_ok_at": prev_last_ok,
            "last_error": f"kpl_upstream_error http_code={http_code}",
            "consecutive_fail": prev_consec + 1,
        }
    if not isinstance(resp, dict) or list_key not in resp:
        return {
            "status": "fail",
            "last_ok_at": prev_last_ok,
            "last_error": "malformed response",
            "consecutive_fail": prev_consec + 1,
        }
    return {
        "status": "ok",
        "last_ok_at": _now_str(),
        "last_error": None,
        "consecutive_fail": 0,
    }


def probe_realtime() -> dict[str, Any]:
    """Probe the KPL realtime endpoint (apphwhq) and update health state."""
    kind = "kpl_realtime_health"
    with _CACHE_LOCK:
        prev = dict(_HEALTH_CACHE.get("realtime", _INITIAL_STATE))

    try:
        client = get_kpl_realtime()
        resp = client.get_market_statistics_lite()
    except Exception as e:
        logger.exception("probe_realtime client exception")
        state = {
            "status": "fail",
            "last_ok_at": prev.get("last_ok_at"),
            "last_error": str(e)[:200],
            "consecutive_fail": int(prev.get("consecutive_fail", 0)) + 1,
        }
    else:
        state = _evaluate(resp, prev, list_key="list")
        if state["status"] == "ok":
            _resolve_alert(kind)
            if prev.get("status") == "fail":
                _send_recovery_email(kind, "realtime")

    with _CACHE_LOCK:
        _HEALTH_CACHE["realtime"] = state

    if state["status"] == "fail":
        is_new = _persist_alert(
            kind,
            "critical",
            f"KPL 实时端点探测失败: {state['last_error']}",
            {"endpoint": "realtime", "last_ok_at": state["last_ok_at"]},
        )
        if is_new:
            _send_alert_email(kind, "realtime", state["last_ok_at"], state["last_error"])

    logger.info(
        "probe_realtime status=%s last_error=%s consecutive_fail=%s",
        state["status"], state["last_error"], state["consecutive_fail"],
    )
    return state


def probe_history() -> dict[str, Any]:
    """Probe the KPL history endpoint (apphis) and update health state."""
    kind = "kpl_history_health"
    with _CACHE_LOCK:
        prev = dict(_HEALTH_CACHE.get("history", _INITIAL_STATE))

    try:
        client = get_kpl_history()
        resp = client.get_history_lite()
    except Exception as e:
        logger.exception("probe_history client exception")
        state = {
            "status": "fail",
            "last_ok_at": prev.get("last_ok_at"),
            "last_error": str(e)[:200],
            "consecutive_fail": int(prev.get("consecutive_fail", 0)) + 1,
        }
    else:
        # daban_pc HisZhangFuDetail 返回顶层 'list' 字段；malformed 检查同 realtime。
        state = _evaluate(resp, prev, list_key="list")
        if state["status"] == "ok":
            _resolve_alert(kind)
            if prev.get("status") == "fail":
                _send_recovery_email(kind, "history")

    with _CACHE_LOCK:
        _HEALTH_CACHE["history"] = state

    if state["status"] == "fail":
        is_new = _persist_alert(
            kind,
            "critical",
            f"KPL 历史端点探测失败: {state['last_error']}",
            {"endpoint": "history", "last_ok_at": state["last_ok_at"]},
        )
        if is_new:
            _send_alert_email(kind, "history", state["last_ok_at"], state["last_error"])

    logger.info(
        "probe_history status=%s last_error=%s consecutive_fail=%s",
        state["status"], state["last_error"], state["consecutive_fail"],
    )
    return state


def trigger_health_probe_now(scope: str = "all") -> dict[str, dict[str, Any]]:
    """Manually fire one or both probes synchronously and return the cache.

    ``scope='realtime'`` / ``'history'`` / ``'all'`` (default). Used by admin
    "force re-check" buttons and by the post-cookie-update flow so the badge
    flips green within a couple of seconds instead of after the next 30min tick.
    """
    if scope in ("realtime", "all"):
        probe_realtime()
    if scope in ("history", "all"):
        probe_history()
    return get_health_cache()


def get_health_cache() -> dict[str, dict[str, Any]]:
    """Return a shallow copy of ``_HEALTH_CACHE`` so callers can't mutate state."""
    with _CACHE_LOCK:
        return {k: dict(v) for k, v in _HEALTH_CACHE.items()}


def _reset_cache_for_tests() -> None:
    """Reset module-level cache to its initial state. Tests only."""
    with _CACHE_LOCK:
        _HEALTH_CACHE["realtime"] = dict(_INITIAL_STATE)
        _HEALTH_CACHE["history"] = dict(_INITIAL_STATE)
