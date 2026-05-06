from __future__ import annotations

import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.routes import ai as ai_module


class _FakeEtfRotationAgent:
    def generate_advice(self, **_kwargs):
        return "ETF轮动分析仅供研究参考，不构成任何投资建议。"


def _client(monkeypatch, *, signals_mode: str, backtest_mode: str) -> TestClient:
    def fake_signals(mode: str = "auto"):
        return {
            "data_mode": signals_mode,
            "data_source": "sample_engine" if signals_mode == "sample" else "tushare_fund_daily",
            "as_of": "2026-05-05",
            "signals": [{"code": "159819", "name": "人工智能ETF", "signal": "持有"}],
        }

    def fake_backtest(mode: str = "auto", years: int = 1):
        return {
            "data_mode": backtest_mode,
            "data_source": "sample_engine" if backtest_mode == "sample" else "tushare_fund_daily",
            "equity_curve": [{"day": 0, "value": 100.0}],
        }

    monkeypatch.setattr(ai_module, "_etf_rotation_agent", _FakeEtfRotationAgent())
    monkeypatch.setattr("packages.features.etf.build_rotation_signals", fake_signals)
    monkeypatch.setattr("packages.features.backtest.run_etf_backtest", fake_backtest)

    app = FastAPI()
    app.include_router(ai_module.router, prefix="/api/ai")
    return TestClient(app)


def test_etf_agent_sample_evidence_is_explicit_mock(monkeypatch):
    client = _client(monkeypatch, signals_mode="sample", backtest_mode="sample")

    resp = client.post("/api/ai/agent/etf-rotation", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "mock"
    assert body["mock"] is True
    assert body["data_mode"] == "sample"
    assert body["data"]["evidence"]["signals"]["data_status"] == "mock"
    assert body["data"]["evidence"]["backtest"]["data_status"] == "mock"
    assert "演示数据" in body["message"]


def test_etf_agent_live_evidence_is_real(monkeypatch):
    client = _client(monkeypatch, signals_mode="live", backtest_mode="live")

    resp = client.post("/api/ai/agent/etf-rotation", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "real"
    assert body["mock"] is False
    assert body["data_mode"] == "live"
    assert body["data"]["evidence"]["signals"]["data_source"] == "tushare_fund_daily"
    assert body["data"]["evidence"]["backtest"]["data_source"] == "tushare_fund_daily"
