import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import replay


def test_sector_ranking_includes_limit_up_members_from_related_plates(monkeypatch):
    monkeypatch.setattr(
        replay._kpl,
        "get_concept_selected",
        lambda trade_date: [
            {"name": "算力", "intensity": 100},
            {"name": "通信", "intensity": 90},
        ],
    )
    monkeypatch.setattr(
        replay._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "000001",
                "stock_name": "测试A",
                "board_count": 2,
                "related_plates": ["通信", "算力"],
                "first_plate_name": "",
            },
            {
                "stock_code": "000002",
                "stock_name": "测试B",
                "board_count": 1,
                "related_plates": ["机器人"],
                "first_plate_name": "机器人",
            },
        ],
    )

    result = replay.sector_ranking(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["data"][0]["name"] == "算力"
    assert result["data"][0]["limit_up_count"] == 1
    assert result["data"][0]["limit_up_members"][0]["stock_code"] == "000001"
    assert result["data"][1]["name"] == "通信"
    assert result["data"][1]["limit_up_count"] == 1


def test_sector_ranking_matches_common_concept_aliases(monkeypatch):
    monkeypatch.setattr(
        replay._kpl,
        "get_concept_selected",
        lambda trade_date: [
            {"name": "算力", "intensity": 100},
            {"name": "机器人概念", "intensity": 90},
        ],
    )
    monkeypatch.setattr(
        replay._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "000066",
                "stock_name": "中国长城",
                "board_count": 3,
                "related_plates": ["计算机设"],
                "first_plate_name": "计算机设",
            },
            {
                "stock_code": "002031",
                "stock_name": "巨轮智能",
                "board_count": 1,
                "related_plates": ["通用设备"],
                "first_plate_name": "通用设备",
            },
        ],
    )

    result = replay.sector_ranking(date="2026-05-07")

    assert result["data"][0]["name"] == "算力"
    assert result["data"][0]["limit_up_members"][0]["stock_code"] == "000066"
    assert result["data"][1]["name"] == "机器人概念"
    assert result["data"][1]["limit_up_members"][0]["stock_code"] == "002031"


def test_sector_ranking_derives_mainline_from_limit_pool_when_concepts_empty(monkeypatch):
    monkeypatch.setattr(replay._kpl, "get_concept_selected", lambda trade_date: [])
    monkeypatch.setattr(
        replay._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "002491",
                "stock_name": "通鼎互联",
                "change_rate": 10.0,
                "board_count": 1,
                "related_plates": ["通信设备"],
                "first_plate_name": "通信设备",
                "amount": 100_000_000,
            },
            {
                "stock_code": "002281",
                "stock_name": "光迅科技",
                "change_rate": 8.9,
                "board_count": 1,
                "related_plates": ["通信设备"],
                "first_plate_name": "通信设备",
                "amount": 50_000_000,
            },
        ],
    )

    result = replay.sector_ranking(date="2026-05-08")

    assert result["data_status"] == "real"
    assert result["source"] == "kpl_pool_derived"
    assert result["data"][0]["name"] == "通信设备"
    assert result["data"][0]["limit_up_count"] == 2
    assert result["data"][0]["net_flow"] == 150_000_000


def test_capital_flow_derives_from_limit_pool_when_concepts_empty(monkeypatch):
    monkeypatch.setattr(replay._kpl, "get_concept_selected", lambda trade_date: [])
    monkeypatch.setattr(
        replay._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "002491",
                "stock_name": "通鼎互联",
                "change_rate": 10.0,
                "board_count": 1,
                "related_plates": ["通信设备"],
                "first_plate_name": "通信设备",
                "amount": 100_000_000,
            },
        ],
    )

    result = replay.capital_flow(date="2026-05-08")

    assert result["data_status"] == "real"
    assert result["data"][0]["name"] == "通信设备"
    assert result["data"][0]["net_flow"] == 100_000_000
