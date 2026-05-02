"""5xx surge alerting service (M001/S08/T01).

Follows the ``_persist_alert`` / ``_resolve_alert`` debounce pattern from
``kpl_health.py`` (MEM059): one unresolved ``system_alerts`` row per kind,
INSERT → email, UPDATE → debounce, recovery → auto-resolve + recovery email.
"""
from __future__ import annotations

import datetime
import json
import logging

from apps.api.db import execute, query_one

logger = logging.getLogger(__name__)

SURGE_THRESHOLD = 10
WINDOW_SECONDS = 300
WINDOW_MINUTES = WINDOW_SECONDS // 60
ALERT_KIND = "api_5xx_surge"


def _persist_alert(kind: str, level: str, message: str, meta: dict) -> bool:
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
    try:
        execute(
            "UPDATE system_alerts SET resolved_at=CURRENT_TIMESTAMP "
            "WHERE kind=? AND resolved_at IS NULL",
            (kind,),
        )
        logger.info("alert kind=%s auto-resolved", kind)
    except Exception:
        logger.exception("auto-resolve failed kind=%s", kind)


def _send_surge_email(count: int) -> None:
    from apps.api.notify.smtp import send_alert
    from apps.api.notify.templates import five_xx_surge_email_body

    try:
        body = five_xx_surge_email_body(count, WINDOW_MINUTES)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        send_alert(f"【智策】API 5xx 突增告警 - {ts}", body)
    except Exception:
        logger.exception("SMTP send_alert failed kind=%s", ALERT_KIND)


def _send_recovery_email() -> None:
    from apps.api.notify.smtp import send_alert
    from apps.api.notify.templates import five_xx_recovery_email_body

    try:
        send_alert("【智策】API 5xx 突增已恢复", five_xx_recovery_email_body())
    except Exception:
        logger.exception("SMTP send recovery failed kind=%s", ALERT_KIND)


def _has_unresolved_alert() -> bool:
    try:
        row = query_one(
            "SELECT id FROM system_alerts "
            "WHERE kind=? AND resolved_at IS NULL LIMIT 1",
            (ALERT_KIND,),
        )
        return row is not None
    except Exception:
        logger.exception("query unresolved alert failed kind=%s", ALERT_KIND)
        return False


def check_5xx_surge() -> None:
    from apps.api.main import get_5xx_count

    count = get_5xx_count(WINDOW_SECONDS)

    if count >= SURGE_THRESHOLD:
        is_new = _persist_alert(
            ALERT_KIND,
            "critical",
            f"API 5xx count {count} in {WINDOW_MINUTES}min",
            {"count": count},
        )
        if is_new:
            _send_surge_email(count)
    else:
        if _has_unresolved_alert():
            _resolve_alert(ALERT_KIND)
            _send_recovery_email()
