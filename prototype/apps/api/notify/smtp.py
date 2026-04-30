"""Standard-library SMTP_SSL alert sender (M001/S03/T06).

Tiny wrapper around ``smtplib.SMTP_SSL`` so ``apps.api.services.kpl_health``
can send Chinese cookie-failure / recovery emails to the operator without
pulling a third-party SMTP dependency.

Failure semantics:
  * ``smtp_*`` settings missing → warn ONCE then return ``False`` (no spam);
  * Any exception from ``smtplib`` / network → ``logger.exception`` + return
    ``False``. We deliberately do NOT write ``system_alerts`` from this path
    (would create a probe-fail → email-fail → alert → probe-fail loop).
"""
from __future__ import annotations

import logging
import smtplib
import threading
from email.mime.text import MIMEText

from apps.api.config import settings

logger = logging.getLogger(__name__)


_WARN_LOCK = threading.Lock()
_WARNED_NOT_CONFIGURED: dict[str, bool] = {"flag": False}


def _reset_warn_flag_for_tests() -> None:
    """Tests-only: clear the once-per-process warning gate."""
    with _WARN_LOCK:
        _WARNED_NOT_CONFIGURED["flag"] = False


def send_alert(subject: str, body: str) -> bool:
    """Send a UTF-8 plain-text alert to the operator's mailbox.

    Returns ``True`` only on a successful ``SMTP_SSL.send_message`` round-trip.
    """
    if not (settings.smtp_host and settings.smtp_user and settings.smtp_pass):
        with _WARN_LOCK:
            if not _WARNED_NOT_CONFIGURED["flag"]:
                logger.warning(
                    "SMTP not configured (host=%s user=%s), alert emails disabled",
                    settings.smtp_host or "<empty>",
                    settings.smtp_user or "<empty>",
                )
                _WARNED_NOT_CONFIGURED["flag"] = True
        return False

    try:
        msg = MIMEText(body, _charset="utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user
        msg["To"] = settings.smtp_user
        with smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=10
        ) as s:
            s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
        logger.info("smtp send_alert ok subject=%s", subject)
        return True
    except Exception:
        logger.exception("smtp send_alert failed subject=%s", subject)
        return False
