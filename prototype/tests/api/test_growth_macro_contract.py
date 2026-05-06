from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes import growth as growth_module


def _client(monkeypatch, *, macro_rows: list[dict] | None = None, prosperity_rows: list[dict] | None = None) -> TestClient:
    monkeypatch.setattr(growth_module, "get_macro_indicators", lambda: macro_rows or [])
    monkeypatch.setattr(growth_module, "get_industry_prosperity", lambda: prosperity_rows or [])

    app = FastAPI()
    app.include_router(growth_module.router, prefix="/api/growth")
    return TestClient(app)


def test_macro_route_reports_hybrid_when_static_references_are_mixed_with_live(monkeypatch):
    client = _client(
        monkeypatch,
        macro_rows=[
            {"name": "PMI", "data_source": "tushare_cn_pmi", "data_mode": "live", "as_of": "2026-04"},
            {
                "name": "LPR-1Y",
                "data_source": "static_macro_reference",
                "data_mode": "static",
                "as_of": "2026-04",
                "fallback_reason": "indicator_not_available_in_current_tushare_adapter",
            },
        ],
    )

    resp = client.get("/api/growth/macro")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "fallback"
    assert body["mock"] is False
    assert body["data_mode"] == "hybrid"
    assert body["as_of"] == "2026-04"
    assert body["fallback_reason"] == "indicator_not_available_in_current_tushare_adapter"


def test_macro_route_reports_sample_fallback_without_silent_real(monkeypatch):
    client = _client(
        monkeypatch,
        macro_rows=[
            {
                "name": "PMI",
                "data_source": "static_macro_sample",
                "data_mode": "sample",
                "as_of": "2026-03",
                "fallback_reason": "tushare_unavailable_or_empty",
            }
        ],
    )

    resp = client.get("/api/growth/macro")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "mock"
    assert body["mock"] is True
    assert body["data_source"] == "static_macro_sample"
    assert body["data_mode"] == "sample"


def test_prosperity_route_reports_live_tushare_status(monkeypatch):
    client = _client(
        monkeypatch,
        prosperity_rows=[
            {
                "industry": "电子",
                "q1": 70,
                "q2": 80,
                "q3": 75,
                "q4": 90,
                "data_source": "tushare_sw_daily",
                "data_mode": "live",
                "as_of": "2026-05-06",
            }
        ],
    )

    resp = client.get("/api/growth/prosperity")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "real"
    assert body["mock"] is False
    assert body["data_source"] == "tushare_sw_daily"
    assert body["data_mode"] == "live"
    assert body["as_of"] == "2026-05-06"
