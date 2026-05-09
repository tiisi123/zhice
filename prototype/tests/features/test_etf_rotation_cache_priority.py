from __future__ import annotations

from packages.features.etf import rotation


class _ExplodingTushareClient:
    configured = False

    def __init__(self):
        raise AssertionError("TushareClient should not be constructed when disk cache is available")


def test_live_series_uses_disk_cache_before_token_check(monkeypatch):
    series = [
        {
            "code": "159819",
            "name": "人工智能ETF",
            "theme": "AI算力",
            "prices": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
            "flows": [1, 1, 1, 1, 1, 1],
            "turnover": [1, 1, 1, 1, 1, 1],
            "dates": ["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04", "2026-05-05", "2026-05-06"],
            "is_live": True,
        }
    ]
    meta = {
        "data_source": "tushare_fund_daily",
        "data_mode": "live",
        "as_of": "2026-05-06",
        "cache_hit": True,
        "cache_stale": False,
    }

    monkeypatch.setattr(rotation, "load_cached_bundle", lambda max_age_seconds: (series, meta, True))
    monkeypatch.setattr(rotation, "TushareClient", _ExplodingTushareClient)

    got_series, got_meta = rotation._build_live_series_bundle()

    assert got_series == series
    assert got_meta["cache_hit"] is True
    assert got_meta["cache_stale"] is False
    assert got_meta["data_source"] == "tushare_fund_daily"
    assert "cache" in got_meta["note"]


class _PartialTushareClient:
    configured = True

    def get_fund_daily(self, ts_code: str, limit: int = 30):
        del limit
        if ts_code.startswith("588000."):
            return [
                {"date": "2026-05-01", "close": 1.0, "amount": 1000},
                {"date": "2026-05-02", "close": 1.1, "amount": 1100},
                {"date": "2026-05-03", "close": 1.2, "amount": 1200},
                {"date": "2026-05-04", "close": 1.3, "amount": 1300},
                {"date": "2026-05-05", "close": 1.4, "amount": 1400},
                {"date": "2026-05-06", "close": 1.5, "amount": 1500},
            ]
        return []

    def close(self):
        pass


def test_live_series_records_tushare_missing_codes(monkeypatch):
    monkeypatch.setattr(rotation, "load_cached_bundle", lambda max_age_seconds: None)
    monkeypatch.setattr(rotation, "TushareClient", _PartialTushareClient)
    monkeypatch.setattr(rotation, "save_cached_bundle", lambda series, meta: None)

    _series, meta = rotation._build_live_series_bundle()

    assert meta["data_mode"] == "hybrid"
    assert meta["fallback_count"] > 0
    assert "tushare_missing_codes" in meta
    assert "512480" in meta["tushare_missing_codes"]
    assert "588000" not in meta["tushare_missing_codes"]
