import json
import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import replay


def test_ladder_relay_fetches_previous_trade_day_when_history_missing(
    monkeypatch, tmp_path
):
    hist_path = tmp_path / "ladder_history.json"
    monkeypatch.setattr(replay, "_LADDER_HIST", hist_path)

    calls: list[str] = []

    def fake_get_limit_up(trade_date: str):
        calls.append(trade_date)
        if trade_date == "2026-05-07":
            return [
                {"stock_code": "000001", "board_count": 2, "seal_amount": 10},
                {"stock_code": "000003", "board_count": 1, "seal_amount": 5},
            ]
        if trade_date == "2026-05-06":
            return [
                {"stock_code": "000001", "board_count": 1, "seal_amount": 8},
                {"stock_code": "000002", "board_count": 1, "seal_amount": 6},
            ]
        return []

    monkeypatch.setattr(replay._kpl, "get_limit_up", fake_get_limit_up)

    result = replay.ladder_relay(date="2026-05-07")

    assert calls == ["2026-05-07", "2026-05-06"]
    assert result["trade_date"] == "2026-05-07"
    assert result["prev_date"] == "2026-05-06"
    assert result["relay"] == [
        {
            "from_tier": 1,
            "from_count": 2,
            "promoted": 1,
            "promoted_codes": ["000001"],
            "survived": 0,
            "broken": 1,
            "broken_codes": ["000002"],
            "relay_rate": 50.0,
        }
    ]

    saved = json.loads(hist_path.read_text(encoding="utf-8"))
    assert sorted(saved.keys()) == ["2026-05-06", "2026-05-07"]


def test_ladder_relay_skips_weekend_for_default_previous_trade_day(
    monkeypatch, tmp_path
):
    hist_path = tmp_path / "ladder_history.json"
    monkeypatch.setattr(replay, "_LADDER_HIST", hist_path)

    calls: list[str] = []

    def fake_get_limit_up(trade_date: str):
        calls.append(trade_date)
        if trade_date == "2026-05-04":
            return [{"stock_code": "000001", "board_count": 2, "seal_amount": 10}]
        if trade_date == "2026-05-01":
            return [{"stock_code": "000001", "board_count": 1, "seal_amount": 8}]
        return []

    monkeypatch.setattr(replay._kpl, "get_limit_up", fake_get_limit_up)

    result = replay.ladder_relay(date="2026-05-04")

    assert calls == ["2026-05-04", "2026-05-01"]
    assert result["prev_date"] == "2026-05-01"
    assert result["relay"][0]["relay_rate"] == 100.0
