import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import theme


def test_sector_list_prefers_limit_pool_derived_member_groups(monkeypatch):
    monkeypatch.setattr(
        theme._kpl,
        "get_concept_selected",
        lambda trade_date: [
            {"PlateID": "801001", "PlateName": "算力", "ChangePercent": 3.2},
        ],
    )
    monkeypatch.setattr(
        theme._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "000001",
                "stock_name": "测试A",
                "change_rate": 10.0,
                "related_plates": ["通信设备"],
            }
        ],
    )

    result = theme.sector_list(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "kpl_mixed"
    assert result["data"][0]["PlateID"] == "kpl_pool_0"
    assert result["data"][0]["PlateName"] == "通信设备"
    assert result["data"][0]["LimitUpNum"] == 1
    assert result["data"][1]["PlateID"] == "801001"


def test_sector_detail_derives_members_from_limit_pool_when_kpl_detail_empty(monkeypatch):
    monkeypatch.setattr(
        theme._kpl,
        "get_concept_selected",
        lambda trade_date: [
            {
                "PlateID": "801001",
                "PlateName": "算力",
                "ChangePercent": 3.2,
                "LimitUpNum": 2,
            }
        ],
    )
    monkeypatch.setattr(theme._kpl, "get_concept_detail", lambda plate_id, trade_date: [])
    theme._kpl.last_error = None
    theme._kpl.last_http_code = None
    monkeypatch.setattr(
        theme._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "000001",
                "stock_name": "测试A",
                "change_rate": 10.0,
                "board_count": 2,
                "related_plates": ["算力", "通信"],
            },
            {
                "stock_code": "000002",
                "stock_name": "测试B",
                "change_rate": 9.9,
                "board_count": 1,
                "related_plates": ["算力"],
            },
        ],
    )

    result = theme.sector_detail("801001", date="2026-05-07")

    assert result["data_status"] == "fallback"
    assert result["source"] == "kpl_pool_derived"
    assert result["count"] == 2
    assert result["data"][0]["SecurityCode"] == "000001"
    assert result["data"][0]["SecurityName"] == "测试A"
    assert result["message"] == "KPL 板块详情为空，已用涨停池按板块名派生成员。"
