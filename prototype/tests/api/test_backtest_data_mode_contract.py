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
from packages.backtest.engine import BacktestDataUnavailable


def _client(monkeypatch, *, board_data=None, etf_data=None) -> TestClient:
    def fake_board_backtest(sub_strategy: str = "首板", mode: str = "auto", years: int = 1):
        del sub_strategy, years
        if mode == "sample":
            return {"data_mode": "sample", "data_source": "sample_engine", "equity_curve": [{"value": 100}]}
        if board_data is None:
            raise BacktestDataUnavailable("KPL live unavailable")
        return board_data

    def fake_etf_backtest(mode: str = "auto", years: int = 1):
        del years
        if mode == "sample":
            return {"data_mode": "sample", "data_source": "sample_engine", "equity_curve": [{"value": 100}]}
        if etf_data is None:
            raise BacktestDataUnavailable("TuShare live unavailable")
        return etf_data

    monkeypatch.setattr(backtest_module, "run_board_backtest", fake_board_backtest)
    monkeypatch.setattr(backtest_module, "run_etf_backtest", fake_etf_backtest)

    app = FastAPI()
    app.include_router(backtest_module.router, prefix="/api/backtest")
    return TestClient(app)


def test_board_backtest_default_auto_does_not_fallback_to_sample(monkeypatch):
    client = _client(monkeypatch)

    resp = client.get("/api/backtest/board-strategy")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert body["mock"] is False
    assert body["data_mode"] == "unavailable"
    assert body["data_source"] == "kpl_limit_up"


def test_etf_backtest_default_auto_does_not_fallback_to_sample(monkeypatch):
    client = _client(monkeypatch)

    resp = client.get("/api/backtest/etf-rotation")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data_status"] == "unavailable"
    assert body["mock"] is False
    assert body["data_mode"] == "unavailable"
    assert body["data_source"] == "tushare_fund_daily"


def test_explicit_sample_backtests_remain_marked_mock(monkeypatch):
    client = _client(monkeypatch)

    board = client.get("/api/backtest/board-strategy?mode=sample").json()
    etf = client.get("/api/backtest/etf-rotation?mode=sample").json()

    assert board["data_status"] == "mock"
    assert board["mock"] is True
    assert board["data_mode"] == "sample"
    assert etf["data_status"] == "mock"
    assert etf["mock"] is True
    assert etf["data_mode"] == "sample"
