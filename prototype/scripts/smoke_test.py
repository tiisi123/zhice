from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from http.client import BadStatusLine
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE = os.environ.get("ZHICE_SMOKE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
WEB_BASE = os.environ.get("ZHICE_SMOKE_WEB_BASE", "http://127.0.0.1:5173").rstrip("/")

WEB_PATHS = [
    "/login",
    "/replay",
    "/intraday",
    "/sentiment",
    "/theme",
    "/hot-events",
    "/stock",
    "/strategy",
    "/recommend",
    "/dashboard",
    "/finance-report",
    "/feature-map",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def request(method: str, url: str, body: dict | None = None, token: str | None = None) -> tuple[int, str]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as res:
            return res.status, res.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, BadStatusLine, OSError) as e:
        return 0, str(e)


def check_web_paths() -> list[CheckResult]:
    results: list[CheckResult] = []
    for path in WEB_PATHS:
        status, text = request("GET", f"{WEB_BASE}{path}")
        ok = status == 200 and "root" in text
        results.append(CheckResult(f"WEB {path}", ok, f"status={status} bytes={len(text)}"))
    return results


def check_api() -> list[CheckResult]:
    results: list[CheckResult] = []
    status, text = request("GET", f"{API_BASE}/api/health")
    results.append(CheckResult("API /api/health", status == 200 and "ok" in text, f"status={status} body={text[:200]}"))

    phone = f"smoke{int(time.time())}"
    status, text = request(
        "POST",
        f"{API_BASE}/api/auth/register",
        {"phone": phone, "password": "smoke123456", "nickname": "Smoke测试"},
    )
    token = ""
    try:
        payload = json.loads(text)
        token = payload.get("token", "")
    except json.JSONDecodeError:
        pass
    results.append(CheckResult("API /api/auth/register", status == 200 and bool(token), f"status={status} phone={phone}"))

    if token:
        for path in ["/api/auth/me", "/api/recommend/templates", "/api/recommend/strategies", "/api/news/timeline?n=10"]:
            status, text = request("GET", f"{API_BASE}{path}", token=token)
            results.append(CheckResult(f"API {path}", status == 200, f"status={status} bytes={len(text)} body={text[:120]}"))
    return results


def main() -> int:
    results = check_web_paths() + check_api()
    failed = [r for r in results if not r.ok]
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.name} - {r.detail}")
    if failed:
        print(f"\nSmoke failed: {len(failed)}/{len(results)} checks failed", file=sys.stderr)
        return 1
    print(f"\nSmoke passed: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
