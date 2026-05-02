"""M001/S08/T01 — 5xx surge alerting tests.

Covers: sliding-window counter, threshold detection, persist/resolve debounce,
email send logic, recovery path, and template content.

DB layer is fully mocked (no engine touch). Tests import main.py symbols
directly for the sliding window, and mock db.execute/query_one for the
monitor service.
"""
from __future__ import annotations

import importlib
import os
import time

import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DEBUG", "True")
    monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleT0=")
    importlib.reload(__import__("apps.api.config", fromlist=["settings"]))


@pytest.fixture
def main_mod():
    """Return the main module with a clean 5xx window."""
    import apps.api.main as m
    m._reset_5xx_window_for_tests()
    return m


@pytest.fixture
def monitor_ctx(monkeypatch):
    """Set up mocks for the five_xx_monitor module.

    Returns a dict with call tracking lists so tests can assert on DB
    writes and email sends without touching a real DB or SMTP server.
    """
    state = {
        "execute_calls": [],
        "query_one_calls": [],
        "alerts_rows": [],
        "smtp_calls": [],
        "unresolved_row": None,
    }

    def mock_execute(sql, params=()):
        state["execute_calls"].append((sql, params))
        return 1

    def mock_query_one(sql, params=()):
        state["query_one_calls"].append((sql, params))
        return state["unresolved_row"]

    def mock_send_alert(subject, body):
        state["smtp_calls"].append((subject, body))
        return True

    import apps.api.services.five_xx_monitor as mod
    monkeypatch.setattr(mod, "execute", mock_execute)
    monkeypatch.setattr(mod, "query_one", mock_query_one)

    import apps.api.notify.smtp as smtp_mod
    monkeypatch.setattr(smtp_mod, "send_alert", mock_send_alert)

    return state, mod


# ── (a) _5xx_window fills on 500 responses ──


def test_5xx_window_fills_on_500(main_mod):
    from apps.api.main import _5xx_window, _5xx_lock

    main_mod._reset_5xx_window_for_tests()
    now = time.time()
    with _5xx_lock:
        _5xx_window.append(now)
        _5xx_window.append(now - 1)
        _5xx_window.append(now - 2)
    assert len(_5xx_window) == 3


# ── (b) get_5xx_count returns correct count within window ──


def test_get_5xx_count_within_window(main_mod):
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(15):
            _5xx_window.append(now - i * 10)
    assert main_mod.get_5xx_count(300) == 15


# ── (c) old entries expire ──


def test_old_entries_expire(main_mod):
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        _5xx_window.append(now - 400)
        _5xx_window.append(now - 500)
        _5xx_window.append(now - 10)
    assert main_mod.get_5xx_count(300) == 1


# ── (d) check_5xx_surge triggers alert at threshold ──


def test_surge_triggers_alert_at_threshold(main_mod, monitor_ctx):
    state, mod = monitor_ctx
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(12):
            _5xx_window.append(now - i)

    mod.check_5xx_surge()

    inserts = [c for c in state["execute_calls"] if "INSERT" in c[0]]
    assert len(inserts) == 1, f"Expected 1 INSERT, got {inserts}"
    assert inserts[0][1][0] == "api_5xx_surge"
    assert len(state["smtp_calls"]) == 1
    assert "5xx" in state["smtp_calls"][0][0]


# ── (e) check_5xx_surge does NOT trigger below threshold ──


def test_no_alert_below_threshold(main_mod, monitor_ctx):
    state, mod = monitor_ctx
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(5):
            _5xx_window.append(now - i)

    mod.check_5xx_surge()

    inserts = [c for c in state["execute_calls"] if "INSERT" in c[0]]
    assert len(inserts) == 0
    assert len(state["smtp_calls"]) == 0


# ── (f) duplicate surge only UPDATEs (no re-email) ──


def test_duplicate_surge_updates_no_reemail(main_mod, monitor_ctx):
    state, mod = monitor_ctx
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(15):
            _5xx_window.append(now - i)

    state["unresolved_row"] = {"id": 42, "meta": '{"retry_count": 1}'}

    mod.check_5xx_surge()

    updates = [c for c in state["execute_calls"] if "UPDATE" in c[0] and "system_alerts" in c[0]]
    assert len(updates) == 1
    inserts = [c for c in state["execute_calls"] if "INSERT" in c[0]]
    assert len(inserts) == 0
    assert len(state["smtp_calls"]) == 0


# ── (g) recovery resolves alert ──


def test_recovery_resolves_alert(main_mod, monitor_ctx):
    state, mod = monitor_ctx
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(3):
            _5xx_window.append(now - i)

    # Simulate existing unresolved alert for the _has_unresolved_alert query
    def mock_query_one_recovery(sql, params=()):
        state["query_one_calls"].append((sql, params))
        if "resolved_at IS NULL" in sql and "api_5xx_surge" in params:
            return {"id": 99}
        return None

    import apps.api.services.five_xx_monitor as mod_ref
    from unittest.mock import patch
    with patch.object(mod_ref, "query_one", mock_query_one_recovery):
        mod.check_5xx_surge()

    resolves = [c for c in state["execute_calls"] if "resolved_at=CURRENT_TIMESTAMP" in c[0]]
    assert len(resolves) == 1
    assert len(state["smtp_calls"]) == 1
    assert "恢复" in state["smtp_calls"][0][0]


# ── (h) email template contains required fields ──


def test_surge_email_template_fields():
    from apps.api.notify.templates import five_xx_surge_email_body

    body = five_xx_surge_email_body(count=15, window_minutes=5)
    assert "15" in body
    assert "5" in body
    assert "docker" in body.lower() or "docker" in body
    assert "智策" in body


def test_recovery_email_template_fields():
    from apps.api.notify.templates import five_xx_recovery_email_body

    body = five_xx_recovery_email_body()
    assert "恢复" in body
    assert "智策" in body


# ── extra: maxlen enforcement ──


def test_5xx_window_maxlen(main_mod):
    from apps.api.main import _5xx_window, _5xx_lock

    now = time.time()
    with _5xx_lock:
        for i in range(1100):
            _5xx_window.append(now - i)
    assert len(_5xx_window) == 1000
