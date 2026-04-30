"""Unit tests for apps.api.notify (M001/S03/T06).

Covers Negative Tests + Must-Haves from
``.gsd/milestones/M001/slices/S03/tasks/T06-PLAN.md``:

  - ``send_alert`` short-circuits + warns ONCE when smtp_* is unset.
  - ``send_alert`` calls ``smtplib.SMTP_SSL`` exactly once on the happy path
    and returns ``True`` after ``send_message``.
  - ``send_alert`` swallows ``socket.gaierror`` / arbitrary exceptions and
    returns ``False`` (so the cron probe never crashes on a flaky relay).
  - Failure email body contains every operator-actionable field
    (probe_kind / http_code / last_ok_at / 业主 admin steps).
  - Recovery email body confirms the green-light wording.

The whole SMTP_SSL transport is mocked at module level — no socket is
opened during these tests. ``DEBUG=True`` is set at import time so the
``validate_required_secrets`` startup gate (which would otherwise raise
``RuntimeError`` for ``ZHICE_JWT_SECRET`` / ``DATABASE_URL`` / etc.)
degrades to a warning — same pattern as ``test_cookie_provider.py``.
"""
from __future__ import annotations

import importlib
import logging
import os
import smtplib
import socket
from unittest.mock import MagicMock, patch

import pytest

# Set DEBUG=True before importing settings so validate_required_secrets stays
# in warning-only mode for the missing JWT_SECRET / DATABASE_URL / etc.
os.environ.setdefault("DEBUG", "True")

from apps.api import config as config_module  # noqa: E402

importlib.reload(config_module)

from apps.api.notify import smtp as smtp_module  # noqa: E402
from apps.api.notify.templates import (  # noqa: E402
    cookie_failure_email_body,
    cookie_recovery_email_body,
)


@pytest.fixture
def configured_smtp(monkeypatch):
    """Pretend the operator already filled in SMTP creds."""
    monkeypatch.setattr(smtp_module.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(smtp_module.settings, "smtp_port", 465)
    monkeypatch.setattr(smtp_module.settings, "smtp_user", "owner@example.com")
    monkeypatch.setattr(smtp_module.settings, "smtp_pass", "supersecret")
    smtp_module._reset_warn_flag_for_tests()
    yield
    smtp_module._reset_warn_flag_for_tests()


@pytest.fixture
def unconfigured_smtp(monkeypatch):
    """Empty smtp_host / user / pass — exercises the warn-once branch."""
    monkeypatch.setattr(smtp_module.settings, "smtp_host", "")
    monkeypatch.setattr(smtp_module.settings, "smtp_user", "")
    monkeypatch.setattr(smtp_module.settings, "smtp_pass", "")
    smtp_module._reset_warn_flag_for_tests()
    yield
    smtp_module._reset_warn_flag_for_tests()


# ---------------------------------------------------------------------------
# send_alert: configuration gating + warn-once
# ---------------------------------------------------------------------------


def test_send_alert_smtp_not_configured_warns_once(unconfigured_smtp, caplog):
    """smtp_host='' → return False + warn ONCE; subsequent calls stay quiet."""
    with caplog.at_level(logging.WARNING, logger=smtp_module.logger.name):
        assert smtp_module.send_alert("subj", "body") is False
        assert smtp_module.send_alert("subj2", "body2") is False

    warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "SMTP not configured" in r.getMessage()
    ]
    assert len(warnings) == 1, (
        "Must warn at most once per process to avoid spamming logs every 30min "
        "tick when the operator has not yet configured SMTP."
    )


# ---------------------------------------------------------------------------
# send_alert: happy path
# ---------------------------------------------------------------------------


def test_send_alert_calls_smtplib_send_message(configured_smtp):
    """Configured creds + working SMTP → exactly one send_message round-trip."""
    fake_smtp = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_smtp
    fake_ctx.__exit__.return_value = False

    with patch.object(smtp_module.smtplib, "SMTP_SSL", return_value=fake_ctx) as ssl_ctor:
        ok = smtp_module.send_alert("【智策】KPL realtime 健康探测失败", "正文 body")

    assert ok is True
    ssl_ctor.assert_called_once_with("smtp.example.com", 465, timeout=10)
    fake_smtp.login.assert_called_once_with("owner@example.com", "supersecret")
    assert fake_smtp.send_message.call_count == 1
    msg_arg = fake_smtp.send_message.call_args.args[0]
    # Subject may be either raw 中文 or the ASCII-encoded =?utf-8?...?= form
    # depending on email.policy version — either is correct.
    subj = msg_arg["Subject"]
    assert "KPL realtime" in subj or subj.startswith("=?")
    assert msg_arg.get_content_charset() == "utf-8"


# ---------------------------------------------------------------------------
# send_alert: error paths
# ---------------------------------------------------------------------------


def test_send_alert_swallows_socket_gaierror(configured_smtp, caplog):
    """SMTP host unreachable → return False, log traceback, never raise."""
    with patch.object(
        smtp_module.smtplib,
        "SMTP_SSL",
        side_effect=socket.gaierror("Name or service not known"),
    ):
        with caplog.at_level(logging.ERROR, logger=smtp_module.logger.name):
            ok = smtp_module.send_alert("subj", "body")

    assert ok is False
    assert any(
        r.levelno >= logging.ERROR and "smtp send_alert failed" in r.getMessage()
        for r in caplog.records
    ), "Failure path must log via logger.exception so 3am debugger has a traceback."


def test_send_alert_swallows_smtp_auth_error(configured_smtp):
    """smtplib.SMTPAuthenticationError → return False without raising."""
    with patch.object(
        smtp_module.smtplib,
        "SMTP_SSL",
        side_effect=smtplib.SMTPAuthenticationError(535, b"bad password"),
    ):
        assert smtp_module.send_alert("subj", "body") is False


# ---------------------------------------------------------------------------
# Templates: Chinese body content
# ---------------------------------------------------------------------------


def test_cookie_failure_email_body_contains_operator_actionables():
    body = cookie_failure_email_body(
        "realtime", 401, "2026-04-30 10:00:00", "cookie expired"
    )

    for needle in (
        "KPL realtime",
        "401",
        "cookie expired",
        "2026-04-30 10:00:00",
        "/admin",
        "KPL Cookie",
    ):
        assert needle in body, f"missing '{needle}' in failure email body"

    # Must never leak the cookie value itself or the smtp_pass into the body.
    assert "supersecret" not in body
    assert "secret_value" not in body


def test_cookie_failure_email_body_handles_none_http_code_and_no_history():
    """http_code=None + last_ok_at=None (first-ever probe) renders cleanly."""
    body = cookie_failure_email_body("history", None, None, "cookie_missing")
    assert "KPL history" in body
    assert "cookie_missing" in body
    # Sentinel wording for missing http_code / last_ok_at.
    assert "未返回" in body
    assert "尚无记录" in body or "首次" in body


def test_cookie_recovery_email_body_contains_recovery_signal():
    body = cookie_recovery_email_body("history")
    assert "KPL history" in body
    assert "已恢复" in body
    assert "智策" in body


# ---------------------------------------------------------------------------
# Architectural guarantee: notify.smtp does NOT touch system_alerts.
# ---------------------------------------------------------------------------


def test_send_alert_does_not_write_system_alerts():
    """send_alert must not import the DB layer or run any SQL — writing
    ``system_alerts`` from this module would create a probe-fail →
    email-fail → alert → probe-fail loop.
    """
    assert smtp_module.__file__, "smtp module must have a source file path"
    with open(smtp_module.__file__, "r", encoding="utf-8") as f:
        text = f.read()
    assert "from apps.api.db" not in text, "must not import db helpers"
    assert "INSERT INTO" not in text.upper(), "must not run INSERT SQL"
    assert "UPDATE " not in text.upper(), "must not run UPDATE SQL"
