import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.ai.context_builders import copilot_orchestrator as copilot


def test_copilot_evidence_derives_sectors_from_limit_up_when_concepts_empty(monkeypatch):
    monkeypatch.setattr(copilot._kpl, "get_market_statistics", lambda trade_date: [])
    monkeypatch.setattr(copilot._kpl, "get_broken", lambda trade_date: [])
    monkeypatch.setattr(copilot._kpl, "get_concept_selected", lambda trade_date: [])
    monkeypatch.setattr(
        copilot._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "002491",
                "stock_name": "通鼎互联",
                "change_rate": 10.0,
                "board_count": 1,
                "related_plates": ["通信设备"],
                "first_plate_name": "通信设备",
                "seal_amount": 100_000_000,
            }
        ],
    )

    evidence = copilot.build_copilot_evidence("今日市场主线是什么？", "/replay", "2026-05-08")

    assert evidence["trade_date"] == "2026-05-08"
    assert evidence["market"]["limit_up_count"] == 1
    assert evidence["sectors"][0]["name"] == "通信设备"
    assert "KPL limit_up derived sectors" in evidence["sources"]
