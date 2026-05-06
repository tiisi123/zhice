from __future__ import annotations

import json
import time

from packages.features.etf.cache import describe_cache, load_cached_bundle, save_cached_bundle


def test_describe_cache_miss(tmp_path):
    path = tmp_path / "missing.json"

    meta = describe_cache(path=path)

    assert meta["cache_hit"] is False
    assert meta["cache_hit_rate"] == 0.0
    assert meta["cache_stale"] is True
    assert meta["data_source"] == "tushare_cache_miss"


def test_load_cached_bundle_fresh(tmp_path):
    path = tmp_path / "etf_live_series.json"
    series = [{"code": "159819", "prices": [1.0, 1.1]}]
    source_meta = {"data_source": "tushare_fund_daily", "data_mode": "live", "as_of": "2026-05-05"}

    save_cached_bundle(series, source_meta, path=path)

    loaded = load_cached_bundle(max_age_seconds=300, path=path)
    assert loaded is not None
    loaded_series, meta, is_fresh = loaded
    assert loaded_series == series
    assert is_fresh is True
    assert meta["cache_hit"] is True
    assert meta["cache_hit_rate"] == 1.0
    assert meta["cache_stale"] is False
    assert meta["data_source"] == "tushare_fund_daily"
    assert meta["as_of"] == "2026-05-05"


def test_load_cached_bundle_stale(tmp_path):
    path = tmp_path / "etf_live_series.json"
    path.write_text(
        json.dumps(
            {
                "stored_at_ts": time.time() - 1000,
                "series": [{"code": "159819"}],
                "meta": {"data_source": "tushare_fund_daily", "data_mode": "live"},
            }
        ),
        encoding="utf-8",
    )

    loaded = load_cached_bundle(max_age_seconds=1, path=path)

    assert loaded is not None
    _series, meta, is_fresh = loaded
    assert is_fresh is False
    assert meta["cache_hit"] is True
    assert meta["cache_stale"] is True
    assert meta["cache_age_seconds"] >= 999
