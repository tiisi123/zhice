"""M001/S06/T01 rotation sentinel tests — cookie_missing + upstream_error → unavailable."""
from __future__ import annotations

import os

os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")
os.environ.setdefault("DEBUG", "True")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes import rotation as rotation_module


class _FakeKpl:
    """Minimal stub for KplClient sentinel protocol."""

    def __init__(self, *, last_error=None, last_http_code=None, sectors=None):
        self.last_error = last_error
        self.last_http_code = last_http_code
        self._sectors = sectors or []

    def get_concept_selected(self, trade_date: str):
        return list(self._sectors)


@pytest.fixture
def rotation_app(monkeypatch):
    """Yield a factory that builds a TestClient with a specific _kpl stub."""

    def _build(*, last_error=None, last_http_code=None, sectors=None):
        fake = _FakeKpl(
            last_error=last_error,
            last_http_code=last_http_code,
            sectors=sectors,
        )
        monkeypatch.setattr(rotation_module, "_kpl", fake)
        app = FastAPI()
        app.include_router(rotation_module.router, prefix="/api/rotation")
        return TestClient(app)

    return _build


def test_novelty_cookie_missing_returns_unavailable(rotation_app):
    client = rotation_app(last_error="cookie_missing")
    resp = client.get("/api/rotation/novelty?date=2026-05-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert "Cookie" in body.get("message", "")
    assert body["source"] == "kpl"


def test_novelty_upstream_error_returns_unavailable(rotation_app):
    client = rotation_app(last_error="kpl_upstream_error", last_http_code=403)
    resp = client.get("/api/rotation/novelty?date=2026-05-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert "403" in body.get("message", "")


def test_novelty_healthy_returns_real(rotation_app, monkeypatch):
    sectors = [{"PlateName": "AI算力", "Intensity": 80, "ChangePercent": 5.2}]
    monkeypatch.setattr(rotation_module, "mark_themes", lambda s, d: s)
    monkeypatch.setattr(rotation_module, "list_recent_new", lambda days=3: [])
    client = rotation_app(sectors=sectors)
    resp = client.get("/api/rotation/novelty?date=2026-05-01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] in ("real", "empty")
    assert body["source"] == "kpl"


def test_theme_history_cookie_missing_returns_unavailable(rotation_app):
    client = rotation_app(last_error="cookie_missing")
    resp = client.get("/api/rotation/theme-history/AI算力?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert "Cookie" in body.get("message", "")


def test_theme_history_upstream_error_returns_unavailable(rotation_app):
    client = rotation_app(last_error="kpl_upstream_error", last_http_code=500)
    resp = client.get("/api/rotation/theme-history/AI算力?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert "500" in body.get("message", "")


def test_theme_history_healthy_returns_real(rotation_app):
    sectors = [{"PlateName": "AI算力", "Intensity": 80, "ChangePercent": 5.2}]
    client = rotation_app(sectors=sectors)
    resp = client.get("/api/rotation/theme-history/AI算力?days=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] in ("real", "empty")
