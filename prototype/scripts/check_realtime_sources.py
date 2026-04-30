from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")

CHECKS = [
    ("/api/market/limit-up", "kpl"),
    ("/api/market/broken", "kpl"),
    ("/api/market/hot-stocks", "kpl"),
    ("/api/market/anomaly", "kpl"),
    ("/api/longhu/rank", "kpl"),
]


@dataclass
class Result:
    path: str
    ok: bool
    detail: str


def get_json(path: str) -> tuple[int, dict | None, str]:
    req = Request(f"{API_BASE}{path}", method="GET")
    try:
        with urlopen(req, timeout=20) as res:
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


def check(path: str, expected_source: str) -> Result:
    status, payload, raw = get_json(path)
    if status != 200:
        return Result(path, False, f"status={status} body={raw[:160]}")
    if not isinstance(payload, dict):
        return Result(path, False, "response is not a JSON object")

    source = str(payload.get("source") or "")
    data_status = str(payload.get("data_status") or "")
    mock = payload.get("mock")
    count = payload.get("count", payload.get("total", len(payload.get("data") or payload.get("items") or [])))

    if not source_matches(source, expected_source):
        return Result(path, False, f"source={source!r}, expected={expected_source!r}")
    if mock is not False:
        return Result(path, False, f"mock must be false, got {mock!r}")
    if data_status not in {"ok", "empty", "partial", "stale", "unavailable", "error"}:
        return Result(path, False, f"invalid data_status={data_status!r}")
    if data_status in {"unavailable", "error"}:
        return Result(path, False, f"data_status={data_status} source={source} count={count}")

    return Result(path, True, f"source={source} data_status={data_status} count={count}")


def main() -> int:
    results = [check(path, expected) for path, expected in CHECKS]
    for item in results:
        mark = "PASS" if item.ok else "FAIL"
        print(f"[{mark}] {item.path} - {item.detail}")
    failed = [item for item in results if not item.ok]
    if failed:
        print(f"\nRealtime source check failed: {len(failed)}/{len(results)} checks failed", file=sys.stderr)
        return 1
    print(f"\nRealtime source check passed: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
