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
