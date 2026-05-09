import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import top_traders as route


def test_top_traders_defaults_to_latest_available_trade_day(monkeypatch):
    calls: list[str] = []

    def fake_longhu(trade_date: str):
        calls.append(trade_date)
        if trade_date == "2026-05-06":
            return [
                {
                    "stock_code": "000001",
                    "stock_name": "测试A",
                    "change_rate": 0.1,
                    "net_amount": 10_000_000,
                    "amount": 20_000_000,
                    "float_mv": 1_000_000_000,
                    "turnover_ratio": 0.12,
                    "concepts": ["算力"],
                    "buy_seats": ["机构专用"],
                    "sell_seats": [],
                    "t_seats": [],
                }
            ]
        return []

    monkeypatch.setattr(route._kpl, "get_longhu_stocks", fake_longhu)
    monkeypatch.setattr(route._kpl, "last_error", None, raising=False)

    result = route.top_traders(date=None)

    assert calls[:3] == ["2026-05-08", "2026-05-07", "2026-05-06"]
    assert result["trade_date"] == "2026-05-06"
    assert result["requested_date"] == "2026-05-08"
    assert result["count"] == 1
    assert result["data_status"] == "real"


def test_top_traders_falls_back_when_explicit_date_is_empty(monkeypatch):
    calls: list[str] = []

    def fake_longhu(trade_date: str):
        calls.append(trade_date)
        if trade_date == "2026-05-06":
            return [
                {
                    "stock_code": "000001",
                    "stock_name": "测试A",
                    "change_rate": 0.1,
                    "net_amount": 10_000_000,
                    "amount": 20_000_000,
                    "float_mv": 1_000_000_000,
                    "turnover_ratio": 0.12,
                    "concepts": ["算力"],
                    "buy_seats": ["机构专用"],
                    "sell_seats": [],
                    "t_seats": [],
                }
            ]
        return []

    monkeypatch.setattr(route._kpl, "get_longhu_stocks", fake_longhu)
    monkeypatch.setattr(route._kpl, "last_error", None, raising=False)

    result = route.top_traders(date="2026-05-07")

    assert calls[:2] == ["2026-05-07", "2026-05-06"]
    assert result["trade_date"] == "2026-05-06"
    assert result["requested_date"] == "2026-05-07"
    assert result["data_status"] == "real"
    assert "2026-05-07" in result["message"]


def test_top_traders_returns_empty_when_no_candidate_has_data(monkeypatch):
    monkeypatch.setattr(route._kpl, "get_longhu_stocks", lambda trade_date: [])
    monkeypatch.setattr(route._kpl, "last_error", None, raising=False)

    result = route.top_traders(date="2026-05-07")

    assert result["trade_date"] == "2026-05-07"
    assert result["requested_date"] == "2026-05-07"
    assert result["data_status"] == "empty"
