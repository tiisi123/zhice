from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")

@dataclass(frozen=True)
class EndpointSpec:
    path: str
    required_keys: set[str] = field(default_factory=set)
    count_keys: tuple[str, ...] = ("count", "total")
    expected_source: str | None = None
    list_key: str | None = None


CORE_ENDPOINTS = [
    EndpointSpec("/api/market/limit-up", {"trade_date", "updated_at", "data"}, expected_source="kpl", list_key="data"),
    EndpointSpec("/api/market/broken", {"trade_date", "updated_at", "data"}, expected_source="kpl", list_key="data"),
    EndpointSpec("/api/market/hot-stocks", {"trade_date", "updated_at", "data"}, expected_source="kpl", list_key="data"),
    EndpointSpec("/api/market/anomaly", {"trade_date", "updated_at", "data"}, expected_source="kpl", list_key="data"),
    EndpointSpec("/api/market/summary", {"trade_date", "updated_at"}, expected_source="kpl"),
    EndpointSpec("/api/market/ladder", {"trade_date", "updated_at", "tiers"}, expected_source="kpl"),
    EndpointSpec("/api/analysis/broken-cases", {"trade_date", "updated_at", "by_reason"}, expected_source="kpl"),
    EndpointSpec(
        "/api/longhu/rank",
        {"trade_date", "updated_at", "rank"},
        expected_source="kpl_longhu_bang",
        list_key="rank",
    ),
    EndpointSpec("/api/theme/sectors", expected_source="kpl", list_key="data"),
]

REQUIRED_KEYS = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"ok", "empty", "partial", "stale", "unavailable", "error"}


@dataclass
class Result:
    path: str
    ok: bool
    detail: str


def get_json(path: str) -> tuple[int, dict | None, str]:
    req = Request(f"{API_BASE}{path}", method="GET")
    try:
        with urlopen(req, timeout=15) as res:
            text = res.read().decode("utf-8", errors="replace")
            return res.status, json.loads(text), text
    except HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text), text
        except json.JSONDecodeError:
            return e.code, None, text
    except (URLError, TimeoutError) as e:
        return 0, None, str(e)
    except json.JSONDecodeError as e:
        return 200, None, f"invalid json: {e}"


def source_matches(actual: str, expected: str) -> bool:
    return actual == expected or actual.startswith(f"{expected}_")


def check_endpoint(spec: EndpointSpec) -> Result:
    path = spec.path
    status, payload, raw = get_json(path)
    if status != 200:
        return Result(path, False, f"status={status} body={raw[:160]}")
    if not isinstance(payload, dict):
        return Result(path, False, "response is not a JSON object")

    required = REQUIRED_KEYS | spec.required_keys
    missing = sorted(required - set(payload.keys()))
    if missing:
        return Result(path, False, f"missing keys={missing}")

    if not any(key in payload for key in spec.count_keys):
        return Result(path, False, f"missing count key, expected one of {list(spec.count_keys)}")

    data_status = payload.get("data_status")
    if data_status not in ALLOWED_STATUS:
        return Result(path, False, f"invalid data_status={data_status!r}")

    if payload.get("mock") is not False:
        return Result(path, False, f"mock must be false, got {payload.get('mock')!r}")

    source = str(payload.get("source") or "")
    if not source:
        return Result(path, False, "source must not be empty")
    if spec.expected_source and not source_matches(source, spec.expected_source):
        return Result(path, False, f"source={source!r}, expected={spec.expected_source!r}")

    count = next((payload.get(key) for key in spec.count_keys if key in payload), "")
    if data_status == "empty" and count not in (0, 0.0):
        return Result(path, False, f"empty response must have zero count, got {count!r}")
    if data_status == "empty" and spec.list_key:
        items = payload.get(spec.list_key)
        if isinstance(items, list) and items:
            return Result(path, False, f"empty response must have empty {spec.list_key}, got {len(items)}")

    count = next((payload.get(key) for key in spec.count_keys if key in payload), "")
    return Result(path, True, f"source={source} data_status={data_status} count={count}")


def main() -> int:
    results = [check_endpoint(spec) for spec in CORE_ENDPOINTS]
    for item in results:
        mark = "PASS" if item.ok else "FAIL"
        print(f"[{mark}] {item.path} - {item.detail}")
    failed = [item for item in results if not item.ok]
    if failed:
        print(f"\nAPI contract failed: {len(failed)}/{len(results)} checks failed", file=sys.stderr)
        return 1
    print(f"\nAPI contract passed: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
