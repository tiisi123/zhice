import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import stock


class FakeTushare:
    configured = True

    def get_stock_basic(self, code: str):
        return {"symbol": code[:6], "name": "贵州茅台", "industry": "白酒"}

    def get_daily_basic_latest(self, code: str):
        return {"trade_date": "20260506", "turnover_rate": 0.42, "pe_ttm": 22.5}

    def get_daily(self, ts_code: str, limit: int = 60):
        return [
            {"date": "2026-05-05", "close": 1680.0, "pct_chg": 1.2},
            {"date": "2026-05-06", "close": 1700.0, "pct_chg": 1.19},
        ]


def test_stock_detail_analyzes_any_code_with_tushare_when_not_in_kpl_pool(monkeypatch):
    monkeypatch.setattr(stock, "get_tushare", lambda: FakeTushare())
    monkeypatch.setattr(stock._kpl, "get_limit_up", lambda trade_date: [])
    monkeypatch.setattr(stock._kpl, "get_broken", lambda trade_date: [])
    monkeypatch.setattr(stock._kpl, "get_hot_stocks", lambda trade_date: [])
    monkeypatch.setattr(
        stock._kpl,
        "get_stock_realtime",
        lambda code: {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "price": 1701.0,
            "change_rate": 1.2,
            "turnover_ratio": 0.5,
            "amount": 2_000_000_000,
            "source": "kpl_new_stock_ranking",
        },
    )

    result = stock.stock_detail("600519", date="2026-05-07")

    assert result["data_status"] == "real"
    assert result["source"] == "tushare+kpl"
    assert result["found"] is True
    assert result["name"] == "贵州茅台"
    assert result["match_source"] is None
    assert result["intraday"]["source"] == "kpl_new_stock_ranking"
    assert result["intraday"]["realtime"]["price"] == 1701.0
    assert result["intraday"]["short_pool"]["in_pool"] is False
    assert result["history"]["source"] == "tushare"
    assert result["history"]["daily"][-1]["date"] == "2026-05-06"
    assert result["data_sources"] == [
        {"name": "历史行情/基本资料/估值", "source": "tushare", "status": "real"},
        {"name": "盘中全市场实时行情", "source": "kpl_new_stock_ranking", "status": "real"},
        {"name": "盘中涨停/炸板/热股事件", "source": "kpl_event_pools", "status": "empty"},
    ]
