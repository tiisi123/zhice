from __future__ import annotations

import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes import backtest as backtest_module
from apps.api.routes import etf as etf_module
from apps.api.routes import growth as growth_module
from apps.api.routes import value as value_module
from packages.backtest.engine import BacktestDataUnavailable


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(etf_module.router, prefix="/api/etf")
    app.include_router(backtest_module.router, prefix="/api/backtest")
    app.include_router(growth_module.router, prefix="/api/growth")
    app.include_router(value_module.router, prefix="/api/value")
    return app


def _assert_prd_meta(body: dict) -> None:
    assert "data_source" in body
    assert "data_mode" in body
    assert "as_of" in body
    assert "fallback_reason" in body


def test_etf_dashboard_exposes_prd_metadata(monkeypatch):
    monkeypatch.setattr(
        etf_module,
        "build_rotation_dashboard",
        lambda source_code=None, mode="auto", **_kwargs: {
            "data_mode": "live",
            "data_source": "tushare_fund_daily",
            "as_of": "2026-05-06",
            "cache_stale": False,
            "fallback_reason": "",
            "data_note": "",
            "metrics": [],
        },
    )

    body = TestClient(_app()).get("/api/etf/rotation/dashboard").json()

    assert body["data_status"] == "real"
    assert body["data_source"] == "tushare_fund_daily"
    assert body["data_mode"] == "live"
    assert body["as_of"] == "2026-05-06"
    _assert_prd_meta(body)


def test_backtest_auto_unavailable_exposes_prd_metadata(monkeypatch):
    monkeypatch.setattr(
        backtest_module,
        "run_etf_backtest",
        lambda mode="auto", years=1: (_ for _ in ()).throw(BacktestDataUnavailable("live unavailable")),
    )

    body = TestClient(_app()).get("/api/backtest/etf-rotation").json()

    assert body["data_status"] == "unavailable"
    assert body["mock"] is False
    assert body["data_source"] == "tushare_fund_daily"
    assert body["data_mode"] == "unavailable"
    assert body["fallback_reason"] == "live_data_unavailable"
    _assert_prd_meta(body)


def test_macro_hybrid_metadata_contract(monkeypatch):
    monkeypatch.setattr(
        growth_module,
        "get_macro_indicators",
        lambda: [
            {"name": "PMI", "data_mode": "live", "data_source": "tushare_cn_pmi", "as_of": "2026-04"},
            {
                "name": "LPR-1Y",
                "data_mode": "static",
                "data_source": "static_macro_reference",
                "as_of": "2026-04",
                "fallback_reason": "indicator_not_available_in_current_tushare_adapter",
            },
        ],
    )

    body = TestClient(_app()).get("/api/growth/macro").json()

    assert body["data_status"] == "fallback"
    assert body["mock"] is False
    assert body["data_mode"] == "hybrid"
    _assert_prd_meta(body)


def test_sample_user_visible_routes_are_not_real(monkeypatch):
    monkeypatch.setattr(value_module, "get_alternative_data", lambda code: [{"metric": "招聘"}])
    monkeypatch.setattr(growth_module, "get_meso_data", lambda industry=None: [{"metric": "库存"}])
    monkeypatch.setattr(growth_module, "simulate_rotation", lambda source: [{"target": "AI/算力"}])

    client = TestClient(_app())
    alternative = client.get("/api/value/alternative/300750").json()
    meso = client.get("/api/growth/meso").json()
    rotation = client.get("/api/growth/rotation").json()
    macro_transmission = client.get("/api/value/macro-transmission/PMI上行").json()

    for body in (alternative, meso, rotation, macro_transmission):
        assert body["data_status"] != "real"
        _assert_prd_meta(body)
    assert alternative["data_status"] == "mock"
    assert meso["data_status"] == "mock"
    assert rotation["data_status"] == "mock"
    assert macro_transmission["data_status"] == "fallback"
