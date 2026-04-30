"""Unit tests for KPL connector split (realtime_client + history_client + facade).

Covers:
  - daban_pc parameter-dict alignment (mock httpx.Client.post, capture data)
  - _recent_5min lunch-break boundary (4 cases)
  - cookie sentinel pattern (cookie='' short-circuit, cookie present, upstream 401)
  - facade legacy 9-method signatures still work via realtime/history delegation

Tests do NOT touch real KPL hosts; httpx.Client.post is monkey-patched per-test.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from packages.connectors.kpl.endpoints import (
    KPL_HISTORY_HOST,
    KPL_REALTIME_HOST,
)
from packages.connectors.kpl.history_client import KplHistoryClient
from packages.connectors.kpl.realtime_client import KplRealtimeClient, _recent_5min


DEVICE_ID = "a59f30e2-5978-3ab5-ac32-d6ae2cc89fd5"


def _mock_response(status_code: int = 200, payload: dict | None = None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _capture_post(payload: dict | None = None):
    """Returns (mock_post, captured) where captured["data"] holds the data dict."""
    captured: dict = {"calls": []}

    def fake_post(url, **kwargs):
        captured["calls"].append({"url": url, **kwargs})
        captured["url"] = url
        captured["data"] = kwargs.get("data")
        captured["headers"] = kwargs.get("headers")
        return _mock_response(200, payload or {"list": []})

    return fake_post, captured


# ------------------------------------------------------------------
# Difference #1: 板块强度（实时）— RealRankingInfo / ZhiShuRanking
# ------------------------------------------------------------------
def test_realtime_sectors_realtime_params_match_daban_pc():
    fake_post, captured = _capture_post()
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)
    fixed_now = datetime.datetime(2026, 5, 1, 10, 7, 12)
    with patch.object(
        client._client, "post", side_effect=fake_post
    ), patch("packages.connectors.kpl.realtime_client.datetime") as dt_mod:
        dt_mod.datetime.now.return_value = fixed_now
        dt_mod.timedelta = datetime.timedelta
        dt_mod.time = datetime.time
        client.get_sectors_realtime(index=0, order=0)
    data = captured["data"]
    assert data["a"] == "RealRankingInfo"
    assert data["c"] == "ZhiShuRanking"
    assert data["DeviceID"] == DEVICE_ID
    assert data["VerSion"] == "5.17.0.0"
    assert data["apiv"] == "w38"
    assert data["PhoneOSNew"] == "1"
    assert data["RStart"] == "0925"
    assert data["Type"] == "-4"
    assert data["old"] == "1"
    assert data["ZSType"] == "7"
    assert data["filterType"] == ""
    assert data["Order"] == "0"
    assert data["Index"] == "0"
    assert data["Token"] == "0"
    assert data["UserID"] == "0"
    # REnd is the recent 5-min boundary string — must be an HHMM 4-digit
    assert isinstance(data["REnd"], str) and len(data["REnd"]) == 4
    assert captured["url"] == KPL_REALTIME_HOST


# ------------------------------------------------------------------
# get_concept_selected — exact data dict per task plan test
# ------------------------------------------------------------------
def test_realtime_concept_selected_params_match_plan():
    fake_post, captured = _capture_post()
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)
    fixed_now = datetime.datetime(2026, 5, 1, 10, 7, 12)
    with patch.object(
        client._client, "post", side_effect=fake_post
    ), patch("packages.connectors.kpl.realtime_client.datetime") as dt_mod:
        dt_mod.datetime.now.return_value = fixed_now
        dt_mod.timedelta = datetime.timedelta
        dt_mod.time = datetime.time
        client.get_concept_selected(index=0, order=0)
    data = captured["data"]
    expected = {
        "PhoneOSNew": "1",
        "DeviceID": DEVICE_ID,
        "VerSion": "5.17.0.0",
        "apiv": "w38",
        "Token": "0",
        "UserID": "0",
        "a": "ConceptSelected",
        "c": "HomeDingPan",
        "RStart": "0925",
        "REnd": "1005",  # 10:07 → floor 5min → 10:05
        "IsZZ": "0",
        "TSZB": "0",
        "IsKZZType": "0",
        "TSZB_Type": "0",
        "filterType": "",
        "Order": "0",
        "Index": "0",
        "st": "20",
    }
    assert data == expected


# ------------------------------------------------------------------
# Difference #2: history concept_detail uses ZhiShuStockList_W8
# ------------------------------------------------------------------
def test_history_concept_detail_uses_W8():
    fake_post, captured = _capture_post()
    client = KplHistoryClient(cookie="X", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        client.get_concept_detail_history("801807", "2026-04-29", index=0)
    data = captured["data"]
    assert data["a"] == "ZhiShuStockList_W8"
    assert data["c"] == "HisHomeDingPan"
    assert data["PlateID"] == "801807"
    assert data["Day"] == "2026-04-29"
    assert data["Type"] == "-4"
    assert data["old"] == "1"
    assert data["ZSType"] == "7"
    assert captured["url"] == KPL_HISTORY_HOST


# ------------------------------------------------------------------
# Difference #5: history market_statistics → HisZhangFuDetail (one-shot)
# ------------------------------------------------------------------
def test_history_market_statistics_method_name_change():
    fake_post, captured = _capture_post()
    client = KplHistoryClient(cookie="X", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        client.get_market_statistics("2026-04-29")
    data = captured["data"]
    assert data["a"] == "HisZhangFuDetail"
    assert data["c"] == "HisHomeDingPan"
    assert data["Day"] == "2026-04-29"


# ------------------------------------------------------------------
# Difference #3: SonPlate_Info on subsection
# ------------------------------------------------------------------
def test_realtime_concept_subsection_uses_SonPlate_Info():
    fake_post, captured = _capture_post()
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        client.get_concept_subsection("801159")
    data = captured["data"]
    assert data["a"] == "SonPlate_Info"
    assert data["c"] == "HomeDingPan"
    assert data["PlateID"] == "801159"
    assert data["IsShow"] == "1"


# ------------------------------------------------------------------
# _recent_5min lunch-break boundary cases (Difference #6)
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "now,expected",
    [
        (datetime.datetime(2026, 5, 1, 11, 0, 0), "1100"),
        (datetime.datetime(2026, 5, 1, 11, 31, 0), "1130"),  # lunch start
        (datetime.datetime(2026, 5, 1, 12, 55, 0), "1130"),  # lunch end
        (datetime.datetime(2026, 5, 1, 14, 55, 0), "1455"),
        (datetime.datetime(2026, 5, 1, 9, 25, 0), "0925"),  # open boundary
        (datetime.datetime(2026, 5, 1, 13, 0, 0), "1300"),  # afternoon open
        (datetime.datetime(2026, 5, 1, 15, 30, 0), "1500"),  # post-close cap
    ],
)
def test_recent_5min_boundaries(now, expected):
    assert _recent_5min(now) == expected


def test_recent_5min_pre_open_raises():
    with pytest.raises(ValueError):
        _recent_5min(datetime.datetime(2026, 5, 1, 9, 24, 0))


# ------------------------------------------------------------------
# Cookie missing sentinel pattern
# ------------------------------------------------------------------
def test_cookie_missing_sentinel_realtime():
    client = KplRealtimeClient(cookie="", device_id=DEVICE_ID)
    with patch.object(client._client, "post") as mock_post:
        result = client._post(KPL_REALTIME_HOST, {"a": "test"}, "realtime")
        assert result == {"_error": "cookie_missing"}
        mock_post.assert_not_called()  # network MUST NOT be hit


def test_cookie_missing_sentinel_history():
    client = KplHistoryClient(cookie="", device_id=DEVICE_ID)
    with patch.object(client._client, "post") as mock_post:
        result = client._post(KPL_HISTORY_HOST, {"a": "test"}, "history")
        assert result == {"_error": "cookie_missing"}
        mock_post.assert_not_called()


def test_cookie_present_no_sentinel():
    fake_post, captured = _capture_post(payload={"list": [{"x": 1}]})
    client = KplRealtimeClient(cookie="real-cookie", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        result = client._post(KPL_REALTIME_HOST, {"a": "test"}, "realtime")
    assert "_error" not in result
    assert result.get("list") == [{"x": 1}]
    # Cookie header should be injected
    assert captured["headers"].get("Cookie") == "real-cookie"


# ------------------------------------------------------------------
# Upstream 401 sentinel
# ------------------------------------------------------------------
def test_upstream_401_sentinel_realtime():
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)

    def fake_post(url, **kwargs):
        return _mock_response(401, {})

    with patch.object(client._client, "post", side_effect=fake_post):
        result = client._post(KPL_REALTIME_HOST, {"a": "test"}, "realtime")
    assert result.get("_error") == "kpl_upstream_error"
    assert result.get("http_code") == 401


def test_upstream_403_sentinel_history():
    client = KplHistoryClient(cookie="X", device_id=DEVICE_ID)

    def fake_post(url, **kwargs):
        return _mock_response(403, {})

    with patch.object(client._client, "post", side_effect=fake_post):
        result = client._post(KPL_HISTORY_HOST, {"a": "test"}, "history")
    assert result.get("_error") == "kpl_upstream_error"
    assert result.get("http_code") == 403


# ------------------------------------------------------------------
# Token / UserID default fill (Difference #7) — Token='0', UserID='0' even when anonymous
# ------------------------------------------------------------------
def test_anonymous_token_userid_fill_with_zero():
    fake_post, captured = _capture_post()
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)  # token='', user_id=''
    fixed_now = datetime.datetime(2026, 5, 1, 10, 7, 12)
    with patch.object(
        client._client, "post", side_effect=fake_post
    ), patch("packages.connectors.kpl.realtime_client.datetime") as dt_mod:
        dt_mod.datetime.now.return_value = fixed_now
        dt_mod.timedelta = datetime.timedelta
        dt_mod.time = datetime.time
        client.get_sectors_realtime()
    data = captured["data"]
    assert data["Token"] == "0"
    assert data["UserID"] == "0"


# ------------------------------------------------------------------
# Lite probes: T05 health-job payloads
# ------------------------------------------------------------------
def test_realtime_lite_probe_payload():
    fake_post, captured = _capture_post(payload={"info": {"market_count": 5000}})
    client = KplRealtimeClient(cookie="X", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        client.get_market_statistics_lite()
    data = captured["data"]
    assert data["a"] == "RealRankingInfo"
    assert data["c"] == "ZhiShuRanking"
    assert data["st"] == "1"
    assert data["Index"] == "0"


def test_history_lite_probe_payload_uses_yesterday():
    fake_post, captured = _capture_post(payload={"info": {"market_count": 5000}})
    client = KplHistoryClient(cookie="X", device_id=DEVICE_ID)
    with patch.object(client._client, "post", side_effect=fake_post):
        client.get_history_lite()
    data = captured["data"]
    assert data["a"] == "HisZhangFuDetail"
    assert data["c"] == "HisHomeDingPan"
    # Day is yesterday's YYYY-MM-DD
    assert data["Day"]
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )
    assert data["Day"] == yesterday


# ------------------------------------------------------------------
# Facade backwards-compatibility: legacy 9-method signatures still work
# ------------------------------------------------------------------
def test_facade_get_market_statistics_delegates_to_history():
    from packages.connectors.kpl.client import KplClient

    facade = KplClient(device_id=DEVICE_ID, cookie="X")
    fake_post, captured = _capture_post(
        payload={"info": {"market_count": 5000}}
    )
    with patch.object(facade._history._client, "post", side_effect=fake_post):
        result = facade.get_market_statistics("2026-04-29")
    # Result is list of one row with market_* keys
    assert isinstance(result, list)
    assert len(result) == 1
    assert "market_market_count" in result[0]


def test_facade_returns_empty_list_when_cookie_missing():
    from packages.connectors.kpl.client import KplClient

    facade = KplClient(device_id=DEVICE_ID, cookie="")  # cookie missing → sentinel
    # No httpx mock — facade should short-circuit via sentinel and return []
    result = facade.get_concept_selected("2026-04-29")  # historical path
    assert result == []
    fixed_now = datetime.datetime(2026, 5, 1, 10, 7, 12)
    with patch(
        "packages.connectors.kpl.realtime_client.datetime"
    ) as dt_mod:
        dt_mod.datetime.now.return_value = fixed_now
        dt_mod.timedelta = datetime.timedelta
        dt_mod.time = datetime.time
        result_today = facade.get_concept_selected()  # realtime path
        assert result_today == []
        result_anomaly = facade.get_market_anomaly()  # realtime
        assert result_anomaly == []
