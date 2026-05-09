import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import theme


def test_theme_sectors_derive_from_limit_pool_when_kpl_concepts_empty(monkeypatch):
    monkeypatch.setattr(theme._kpl, "get_concept_selected", lambda trade_date: [])
    monkeypatch.setattr(
        theme._kpl,
        "get_limit_up",
        lambda trade_date: [
            {
                "stock_code": "000001",
                "stock_name": "测试A",
                "change_rate": 10.0,
                "related_plates": ["算力", "通信"],
            },
            {
                "stock_code": "000002",
                "stock_name": "测试B",
                "change_rate": 9.9,
                "related_plates": ["算力"],
            },
        ],
    )

    result = theme.sector_list(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "kpl_pool_derived"
    assert result["count"] == 2
    assert result["data"][0]["PlateName"] == "算力"
    assert result["data"][0]["LimitUpNum"] == 2


def test_theme_list_derive_from_sectors_when_home_theme_list_unavailable(monkeypatch):
    monkeypatch.setattr(theme._kpl, "get_theme_list", lambda trade_date: [])
    monkeypatch.setattr(theme._kpl, "get_limit_up", lambda trade_date: [])
    monkeypatch.setattr(
        theme._kpl,
        "get_concept_selected",
        lambda trade_date: [
            {"PlateID": "801001", "PlateName": "算力", "ChangePercent": 3.2}
        ],
    )

    result = theme.theme_list(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "kpl_sector_derived"
    assert result["data"][0]["Name"] == "算力"


def test_theme_library_uses_kpl_theme_list_contract(monkeypatch):
    monkeypatch.setattr(theme, "_read_theme_library_cache", lambda: ([], ""))
    theme._kpl.last_error = None
    theme._kpl.last_http_code = None
    monkeypatch.setattr(
        theme._kpl,
        "get_theme_list",
        lambda trade_date: [
            {
                "ID": "297",
                "Name": "AI应用",
                "HotNum": 99,
                "LimitUpNum": 3,
                "CreateTime": "2026-05-07 15:00:00",
            }
        ],
    )

    result = theme.theme_library(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "kpl_theme_library"
    assert result["count"] == 1
    assert result["data"][0]["theme_id"] == "297"
    assert result["data"][0]["theme_name"] == "AI应用"
    assert result["data"][0]["theme_zt_num"] == 3


def test_theme_library_detail_falls_back_to_library_row_when_detail_empty(monkeypatch):
    monkeypatch.setattr(theme, "_read_theme_library_cache", lambda: ([], ""))
    theme._kpl.last_error = None
    theme._kpl.last_http_code = None
    monkeypatch.setattr(theme._kpl, "get_theme_library_detail", lambda theme_id: {})
    monkeypatch.setattr(
        theme._kpl,
        "get_theme_list",
        lambda trade_date: [{"ID": "297", "Name": "AI应用", "LimitUpNum": 3}],
    )
    monkeypatch.setattr(theme._kpl, "get_limit_up", lambda trade_date: [])

    result = theme.theme_library_detail("297", date="2026-05-07")

    assert result["data_status"] == "fallback"
    assert result["source"] == "kpl"
    assert result["data"]["theme_id"] == "297"
    assert result["data"]["theme_name"] == "AI应用"
    assert result["data"]["theme_sub_detail"] == []
    assert "细分个股与正文待 KPL 详情恢复" in result["message"]


def test_theme_library_prefers_collected_cache(monkeypatch):
    monkeypatch.setattr(
        theme,
        "_read_theme_library_cache",
        lambda: (
            [
                {"theme_id": "25", "theme_name": "AI硬件", "theme_hot_num": 10, "theme_zt_num": 2},
                {"theme_id": "355", "theme_name": "国产芯片概念", "theme_hot_num": 99, "theme_zt_num": 1},
            ],
            "external_kpl_home_theme_mes",
        ),
    )
    monkeypatch.setattr(theme, "_match_theme_to_market", lambda row, trade_date: {"matched": False})

    result = theme.theme_library(date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "external_kpl_home_theme_mes"
    assert result["data"][0]["theme_name"] == "国产芯片概念"


def test_theme_library_detail_enriches_members_with_kpl_ranking(monkeypatch):
    monkeypatch.setattr(theme, "_read_theme_library_cache", lambda: ([], ""))
    theme._kpl.last_error = None
    theme._kpl.last_http_code = None
    monkeypatch.setattr(
        theme._kpl,
        "get_theme_library_detail",
        lambda theme_id: {
            "theme_id": "297",
            "theme_name": "AI应用",
            "theme_sub_detail": [
                {"stock_code": "300001", "stock_name": "测试科技", "stock_tag_name": "算力"}
            ],
        },
    )
    monkeypatch.setattr(
        theme._kpl,
        "get_stock_ranking",
        lambda date="": [
            {
                "stock_code": "300001",
                "stock_name": "测试科技",
                "price": 12.34,
                "change_rate": 9.91,
                "turnover_ratio": 6.7,
                "amount": 123000000,
                "net_flow": 45000000,
                "ranking_score": 88,
            }
        ],
    )
    monkeypatch.setattr(theme, "_match_theme_to_market", lambda row, trade_date: {"matched": True, "best_match": {"plate_name": "AI应用"}})

    result = theme.theme_library_detail("297", date="2026-05-07")

    member = result["data"]["theme_sub_detail"][0]
    assert result["data_status"] == "real"
    assert result["data"]["quote_match_status"] == "matched"
    assert member["quote_status"] == "matched"
    assert member["change_rate"] == 9.91


def test_match_theme_to_market_normalized_contains(monkeypatch):
    monkeypatch.setattr(
        theme,
        "sector_list",
        lambda date=None: {
            "source": "kpl",
            "data": [
                {"PlateID": "801001", "PlateName": "国产芯片", "Intensity": 80, "LimitUpNum": 3}
            ],
        },
    )

    result = theme._match_theme_to_market({"theme_name": "国产芯片概念"}, "2026-05-07")

    assert result["matched"] is True
    assert result["best_match"]["plate_name"] == "国产芯片"
    assert result["best_match"]["match_rule"] == "normalized_equal"
