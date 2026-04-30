"""M001/S03/T04 admin route integration — require_admin + cookie / alerts CRUD.

Covers the Negative Tests + Must-Haves block from
``.gsd/milestones/M001/slices/S03/tasks/T04-PLAN.md``:

- 普通用户 GET /api/admin/kpl-cookie → 403
- admin GET /api/admin/kpl-cookie → 200, ``has_cookie`` + ``last_updated_at``,
  payload **never** carries ``secret_value``.
- admin POST /api/admin/kpl-cookie body=``{"cookie":"ABC"}`` → 200; subsequent
  ``cookie_provider.get_kpl_cookie()`` returns ``"ABC"``; the persisted
  ``UPDATE system_secrets`` payload is ciphertext, not plaintext.
- POST cookie='' → 422 (Pydantic ``min_length=1``)
- POST cookie='X' * 4097 → 422 (Pydantic ``max_length=4096``)
- POST /api/admin/alerts/99999/ack → 404
- GET /api/admin/alerts?kind=...&unresolved=1 → only un-acked rows for that
  kind.
- POST /api/admin/alerts/{id}/ack → ``resolved_at`` is written.

DB layer is fully mocked (no MySQL/SQLite engine touch). ENCRYPTION_KEY +
DEBUG=True are set BEFORE importing ``apps.api.config`` so Fernet initializes
deterministically; ``cookie_provider`` is reloaded so its module-level
``_fernet`` picks up the test key.

Why a per-test minimal FastAPI app instead of importing ``apps.api.main``:
``main.py`` triggers the APScheduler / WS hub / ``init_db`` admin seed at
import time. We only want the admin router under test, so we mount it on a
fresh ``FastAPI()`` and override the ``current_user`` dependency to inject
admin / non-admin user dicts.
"""
from __future__ import annotations

import importlib

import pytest
from cryptography.fernet import Fernet


_ADMIN_USER = {
    "id": 1,
    "phone": "admin",
    "vip_level": "pro",
    "nickname": "管理员",
}
_NORMAL_USER = {
    "id": 2,
    "phone": "13800138000",
    "vip_level": "free",
    "nickname": "普通用户",
}


@pytest.fixture
def admin_ctx(monkeypatch):
    """Build a minimal FastAPI app mounting only the admin router.

    Returns a dict with ``app`` (TestClient-ready), ``cp`` (reloaded
    cookie_provider module), ``current_user_dep`` (the dependency callable to
    override), and ``db_state`` (in-memory mocks the tests can mutate).
    """
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", test_key)
    monkeypatch.setenv("DEBUG", "True")

    # Reload config + cookie_provider so Fernet initializes against the test key.
    from apps.api import config as config_module
    importlib.reload(config_module)
    from apps.api.services import cookie_provider as cp
    importlib.reload(cp)
    cp._reset_cache_for_tests()

    # Now import the admin router. Its module-level
    # ``from apps.api.db import execute, query_all, query_one`` binds the real
    # functions; we monkeypatch them on both ``apps.api.db`` (so
    # cookie_provider's *function-scope* db imports also see the mocks) and
    # the ``admin`` module's local names (so the route bodies see the mocks).
    from apps.api.routes import admin as admin_module

    db_state: dict = {
        "execute_calls": [],
        "query_one_calls": [],
        "query_all_calls": [],
        "alerts": [],
    }

    def mock_execute(sql, params=()):
        params = tuple(params)
        db_state["execute_calls"].append((sql, params))
        if "UPDATE system_alerts" in sql and "resolved_at" in sql:
            alert_id = params[0]
            for a in db_state["alerts"]:
                if a["id"] == alert_id:
                    a["resolved_at"] = "2026-05-01 00:00:00"
        return 1

    def mock_query_one(sql, params=()):
        params = tuple(params)
        db_state["query_one_calls"].append((sql, params))
        if "system_secrets" in sql:
            return None  # default: no cookie row yet
        if "system_alerts" in sql:
            alert_id = params[0]
            for a in db_state["alerts"]:
                if a["id"] == alert_id:
                    return {"id": alert_id}
            return None
        return None

    def mock_query_all(sql, params=()):
        params = tuple(params)
        db_state["query_all_calls"].append((sql, params))
        if "system_alerts" in sql:
            rows = list(db_state["alerts"])
            param_idx = 0
            if "kind = ?" in sql:
                kind = params[param_idx]
                rows = [r for r in rows if r.get("kind") == kind]
                param_idx += 1
            if "resolved_at IS NULL" in sql:
                rows = [r for r in rows if r.get("resolved_at") is None]
            # final ``LIMIT ?`` placeholder consumed last; we ignore it for
            # in-memory mocks but still validate the param shape.
            return rows
        return []

    import apps.api.db as db
    monkeypatch.setattr(db, "execute", mock_execute, raising=True)
    monkeypatch.setattr(db, "query_one", mock_query_one, raising=True)
    monkeypatch.setattr(db, "query_all", mock_query_all, raising=True)
    monkeypatch.setattr(admin_module, "execute", mock_execute, raising=True)
    monkeypatch.setattr(admin_module, "query_one", mock_query_one, raising=True)
    monkeypatch.setattr(admin_module, "query_all", mock_query_all, raising=True)

    from fastapi import FastAPI
    from apps.api.auth.deps import current_user

    app = FastAPI()
    app.include_router(admin_module.router, prefix="/api/admin", tags=["admin"])

    return {
        "app": app,
        "cp": cp,
        "current_user_dep": current_user,
        "db_state": db_state,
    }


def _client(ctx, user_dict):
    """TestClient with ``current_user`` dependency forced to ``user_dict``."""
    from fastapi.testclient import TestClient

    ctx["app"].dependency_overrides[ctx["current_user_dep"]] = lambda: user_dict
    return TestClient(ctx["app"])


# ---------------------------------------------------------------------------
# GET /api/admin/kpl-cookie
# ---------------------------------------------------------------------------


def test_admin_kpl_cookie_get_requires_admin(admin_ctx):
    """普通用户 GET /api/admin/kpl-cookie → 403."""
    client = _client(admin_ctx, _NORMAL_USER)
    resp = client.get("/api/admin/kpl-cookie")
    assert resp.status_code == 403
    assert "管理员" in resp.json().get("detail", "")


def test_admin_kpl_cookie_get_returns_metadata_only(admin_ctx):
    """admin GET → 200; redaction: ``secret_value`` is *never* serialized."""
    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.get("/api/admin/kpl-cookie")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "has_cookie" in body
    assert "last_updated_at" in body
    assert "last_ok_realtime" in body
    assert "last_ok_history" in body
    assert "secret_value" not in body  # critical redaction
    # Cold-start: no cookie row yet.
    assert body["has_cookie"] is False


# ---------------------------------------------------------------------------
# POST /api/admin/kpl-cookie
# ---------------------------------------------------------------------------


def test_admin_kpl_cookie_post_writes_db(admin_ctx):
    """admin POST {cookie:'ABC'} → 200; cookie_provider.get_kpl_cookie() == 'ABC'."""
    cp = admin_ctx["cp"]
    state = admin_ctx["db_state"]
    cp._reset_cache_for_tests()

    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/kpl-cookie", json={"cookie": "ABC"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True

    # set_kpl_cookie populates the in-memory cache, so the next read returns the plaintext.
    assert cp.get_kpl_cookie() == "ABC"

    update_calls = [c for c in state["execute_calls"] if "UPDATE system_secrets" in c[0]]
    assert len(update_calls) == 1, "exactly one UPDATE system_secrets per POST"
    persisted = update_calls[0][1][0]
    assert persisted != "ABC", "DB must store ciphertext, not plaintext"
    assert cp.decrypt(persisted) == "ABC"

    # updated_by must be threaded through.
    assert update_calls[0][1][1] == _ADMIN_USER["id"]


def test_admin_kpl_cookie_post_too_long_returns_422(admin_ctx):
    """cookie='X' * 4097 → 422 (Pydantic max_length=4096)."""
    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/kpl-cookie", json={"cookie": "X" * 4097})
    assert resp.status_code == 422


def test_admin_kpl_cookie_post_empty_returns_422(admin_ctx):
    """cookie='' → 422 (Pydantic min_length=1)."""
    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/kpl-cookie", json={"cookie": ""})
    assert resp.status_code == 422


def test_admin_kpl_cookie_post_requires_admin(admin_ctx):
    """普通用户 POST /api/admin/kpl-cookie → 403."""
    client = _client(admin_ctx, _NORMAL_USER)
    resp = client.post("/api/admin/kpl-cookie", json={"cookie": "X"})
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/admin/health/kpl  (T05 wired in — admin route now reads _HEALTH_CACHE)
# ---------------------------------------------------------------------------


def test_admin_health_kpl_returns_cache_state(admin_ctx, monkeypatch):
    """T05 present → admin route returns the in-memory cache shape."""
    from apps.api.services import kpl_health

    monkeypatch.setattr(
        kpl_health,
        "get_health_cache",
        lambda: {
            "realtime": {"status": "ok", "last_ok_at": "2026-05-01 12:00:00",
                         "last_error": None, "consecutive_fail": 0},
            "history": {"status": "fail", "last_ok_at": None,
                        "last_error": "cookie_missing", "consecutive_fail": 0},
        },
    )

    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.get("/api/admin/health/kpl")
    assert resp.status_code == 200
    body = resp.json()
    assert body["realtime"]["status"] == "ok"
    assert body["history"]["status"] == "fail"
    assert body["history"]["last_error"] == "cookie_missing"


def test_admin_health_kpl_trigger_runs_probes(admin_ctx, monkeypatch):
    """T05 present → admin POST trigger calls trigger_health_probe_now('all')."""
    from apps.api.services import kpl_health

    calls: list[str] = []

    def fake_trigger(scope: str = "all") -> dict:
        calls.append(scope)
        return {"realtime": {"status": "ok"}, "history": {"status": "ok"}}

    monkeypatch.setattr(kpl_health, "trigger_health_probe_now", fake_trigger)

    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/health/kpl/trigger")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["triggered"] is True
    assert calls == ["all"]


# ---------------------------------------------------------------------------
# GET /api/admin/alerts
# ---------------------------------------------------------------------------


def test_admin_alerts_list_kind_unresolved_filter(admin_ctx):
    """已有 1 行未 ack 告警 → GET /api/admin/alerts count >= 1。"""
    state = admin_ctx["db_state"]
    state["alerts"].append(
        {
            "id": 1,
            "kind": "kpl_realtime_health",
            "level": "warn",
            "message": "Cookie expired",
            "meta": "{}",
            "resolved_at": None,
            "created_at": "2026-05-01 00:00:00",
        }
    )
    state["alerts"].append(
        {
            "id": 2,
            "kind": "kpl_history_health",
            "level": "warn",
            "message": "history down",
            "meta": "{}",
            "resolved_at": "2026-05-01 00:30:00",  # already acked
            "created_at": "2026-05-01 00:00:00",
        }
    )

    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.get("/api/admin/alerts?kind=kpl_realtime_health&unresolved=1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1
    assert body["alerts"][0]["kind"] == "kpl_realtime_health"
    assert body["alerts"][0]["resolved_at"] is None


def test_admin_alerts_requires_admin(admin_ctx):
    """普通用户 GET /api/admin/alerts → 403."""
    client = _client(admin_ctx, _NORMAL_USER)
    resp = client.get("/api/admin/alerts")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/admin/alerts/{id}/ack
# ---------------------------------------------------------------------------


def test_admin_alerts_ack_404(admin_ctx):
    """不存在的 alert id → 404 + 中文 detail."""
    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/alerts/99999/ack")
    assert resp.status_code == 404
    assert "告警不存在" in resp.json().get("detail", "")


def test_admin_alerts_ack_marks_resolved(admin_ctx):
    """已存在的 alert id → 200，``resolved_at`` 被写入。"""
    state = admin_ctx["db_state"]
    state["alerts"].append(
        {
            "id": 7,
            "kind": "kpl_history_health",
            "level": "warn",
            "message": "down",
            "meta": "{}",
            "resolved_at": None,
            "created_at": "2026-05-01 00:00:00",
        }
    )
    client = _client(admin_ctx, _ADMIN_USER)
    resp = client.post("/api/admin/alerts/7/ack")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["alert_id"] == 7

    # Mock side-effect: resolved_at should now be set.
    row = next(a for a in state["alerts"] if a["id"] == 7)
    assert row["resolved_at"] is not None
