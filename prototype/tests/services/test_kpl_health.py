"""Unit tests for apps.api.services.kpl_health (M001/S03/T05).

Covers Negative Tests + Must-Haves from
``.gsd/milestones/M001/slices/S03/tasks/T05-PLAN.md``:

  - probe_realtime success → ``_HEALTH_CACHE['realtime'].status == 'ok'`` and
    ``last_ok_at`` populated, ``consecutive_fail`` reset to 0
  - probe_realtime cookie_missing sentinel → status=fail, last_error
    ``cookie_missing`` and ``consecutive_fail`` does NOT increment (avoids
    daily alert email storm while operator is refreshing the cookie)
  - probe_realtime upstream 4xx sentinel → consecutive_fail += 1, last_error
    contains the http_code
  - probe_realtime malformed (200 but missing 'list') → status=fail
  - probe_realtime exception (network blow-up) inserts a system_alerts row
    on the FIRST failure, UPDATEs the same row on subsequent failures
    (debounce — never two INSERTs in a row)
  - probe_realtime recovery (fail → success) calls _resolve_alert which
    issues an UPDATE … SET resolved_at clause
  - get_health_cache returns a shallow copy that callers cannot mutate to
    poison the source dict
  - trigger_health_probe_now scope='realtime' fires only the realtime probe
  - trigger_health_probe_now scope='all' fires both probes

DB layer is fully mocked at the kpl_health module level — the registry
factories are also monkeypatched so no real httpx call is made.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from apps.api.services import kpl_health


@pytest.fixture
def mock_db(monkeypatch):
    """Replace ``execute`` / ``query_one`` with MagicMocks at module level."""
    execute_mock = MagicMock(return_value=1)
    query_one_mock = MagicMock(return_value=None)
    monkeypatch.setattr(kpl_health, "execute", execute_mock)
    monkeypatch.setattr(kpl_health, "query_one", query_one_mock)
    kpl_health._reset_cache_for_tests()
    return {"execute": execute_mock, "query_one": query_one_mock}


@pytest.fixture
def mock_clients(monkeypatch):
    """Stub out the registry factories — no real httpx call."""
    rt_client = MagicMock()
    hi_client = MagicMock()
    monkeypatch.setattr(kpl_health, "get_kpl_realtime", lambda: rt_client)
    monkeypatch.setattr(kpl_health, "get_kpl_history", lambda: hi_client)
    return {"realtime": rt_client, "history": hi_client}


def _statements(execute_mock: MagicMock) -> list[str]:
    return [call.args[0] for call in execute_mock.call_args_list]


# ---------------------------------------------------------------------------
# probe_realtime: success / known sentinels / malformed / exception
# ---------------------------------------------------------------------------


def test_probe_realtime_success(mock_db, mock_clients):
    mock_clients["realtime"].get_market_statistics_lite.return_value = {
        "list": [{"id": 1}]
    }
    state = kpl_health.probe_realtime()
    assert state["status"] == "ok"
    assert state["last_ok_at"] is not None
    assert state["consecutive_fail"] == 0
    cache = kpl_health.get_health_cache()
    assert cache["realtime"]["status"] == "ok"


def test_probe_realtime_cookie_missing_does_not_increment_consecutive_fail(
    mock_db, mock_clients
):
    """cookie_missing is a known operator-actionable state. Do NOT count it
    against ``consecutive_fail``; otherwise we would page the user every 30min
    even though we know the cookie is empty."""
    mock_clients["realtime"].get_market_statistics_lite.return_value = {
        "_error": "cookie_missing"
    }
    # Pre-set consecutive_fail=2 to verify it stays at 2.
    kpl_health._HEALTH_CACHE["realtime"]["consecutive_fail"] = 2

    state = kpl_health.probe_realtime()

    assert state["status"] == "fail"
    assert state["last_error"] == "cookie_missing"
    assert state["consecutive_fail"] == 2  # unchanged


def test_probe_realtime_upstream_error_records_http_code(mock_db, mock_clients):
    mock_clients["realtime"].get_market_statistics_lite.return_value = {
        "_error": "kpl_upstream_error",
        "http_code": 401,
    }
    state = kpl_health.probe_realtime()
    assert state["status"] == "fail"
    assert "401" in state["last_error"]
    assert state["consecutive_fail"] == 1


def test_probe_realtime_malformed_response(mock_db, mock_clients):
    mock_clients["realtime"].get_market_statistics_lite.return_value = {}
    state = kpl_health.probe_realtime()
    assert state["status"] == "fail"
    assert state["last_error"] == "malformed response"
    assert state["consecutive_fail"] == 1


# ---------------------------------------------------------------------------
# system_alerts INSERT/UPDATE debounce + recovery
# ---------------------------------------------------------------------------


def test_probe_realtime_failure_inserts_then_updates_existing(mock_db, mock_clients):
    """First failure → INSERT (no existing unresolved row).
    Subsequent failure → UPDATE the same row, never another INSERT."""
    mock_clients["realtime"].get_market_statistics_lite.side_effect = RuntimeError(
        "network down"
    )

    # Round 1 — query_one returns None, so kpl_health INSERTs.
    mock_db["query_one"].return_value = None
    kpl_health.probe_realtime()

    inserts = [s for s in _statements(mock_db["execute"]) if "INSERT" in s]
    assert len(inserts) == 1, "first fail must INSERT exactly once"

    # Round 2 — query_one returns the existing row; kpl_health UPDATEs message/meta.
    mock_db["query_one"].return_value = {
        "id": 7,
        "meta": json.dumps({"retry_count": 1}),
    }
    kpl_health.probe_realtime()

    inserts = [s for s in _statements(mock_db["execute"]) if "INSERT" in s]
    updates = [s for s in _statements(mock_db["execute"]) if "UPDATE" in s]
    assert len(inserts) == 1, "must NOT INSERT a second time (debounce)"
    # The UPDATE on the existing row contains 'WHERE id=?' — distinguish it
    # from the recovery UPDATE which contains 'resolved_at'.
    debounce_updates = [s for s in updates if "resolved_at" not in s]
    assert len(debounce_updates) >= 1, "second fail must UPDATE existing row"


def test_probe_realtime_recovery_resolves_alert(mock_db, mock_clients):
    """Probe success after a prior failure → UPDATE resolved_at on every
    matching unresolved row of the same kind."""
    mock_clients["realtime"].get_market_statistics_lite.return_value = {
        "list": [{"id": 1}]
    }

    kpl_health.probe_realtime()

    resolves = [s for s in _statements(mock_db["execute"]) if "resolved_at" in s]
    assert len(resolves) == 1, "success must auto-resolve unresolved alerts"


# ---------------------------------------------------------------------------
# get_health_cache + trigger_health_probe_now
# ---------------------------------------------------------------------------


def test_get_health_cache_returns_shallow_copy(mock_db, mock_clients):
    """Callers must not be able to mutate the source cache through the snapshot."""
    snap = kpl_health.get_health_cache()
    snap["realtime"]["status"] = "tampered"

    fresh = kpl_health.get_health_cache()
    assert fresh["realtime"]["status"] != "tampered"


def test_trigger_health_probe_now_scope_realtime(mock_db, mock_clients):
    mock_clients["realtime"].get_market_statistics_lite.return_value = {"list": [{}]}
    mock_clients["history"].get_history_lite.return_value = {"list": [{}]}

    kpl_health.trigger_health_probe_now(scope="realtime")

    assert mock_clients["realtime"].get_market_statistics_lite.call_count == 1
    assert mock_clients["history"].get_history_lite.call_count == 0


def test_trigger_health_probe_now_scope_all(mock_db, mock_clients):
    mock_clients["realtime"].get_market_statistics_lite.return_value = {"list": [{}]}
    mock_clients["history"].get_history_lite.return_value = {"list": [{}]}

    cache = kpl_health.trigger_health_probe_now(scope="all")

    assert mock_clients["realtime"].get_market_statistics_lite.call_count == 1
    assert mock_clients["history"].get_history_lite.call_count == 1
    assert cache["realtime"]["status"] == "ok"
    assert cache["history"]["status"] == "ok"


# ---------------------------------------------------------------------------
# probe_history parity check (smoke — sentinel handling shared via _evaluate)
# ---------------------------------------------------------------------------


def test_probe_history_success_resets_consecutive_fail(mock_db, mock_clients):
    kpl_health._HEALTH_CACHE["history"]["consecutive_fail"] = 5
    mock_clients["history"].get_history_lite.return_value = {"list": [{}]}

    state = kpl_health.probe_history()

    assert state["status"] == "ok"
    assert state["consecutive_fail"] == 0
