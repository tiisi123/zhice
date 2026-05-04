"""S01 slice verification — exercises /value/screen and /value/financial/{code} against live server.

Tests D004 contract fields (source, data_status, mock) and validates real data flow
for the DFCF-primary → TuShare-fallback cascade (D009).
"""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")

D004_REQUIRED = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}


def get(path: str) -> tuple[int, dict | None]:
    req = Request(f"{API_BASE}{path}", method="GET")
    try:
        with urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read().decode())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except (json.JSONDecodeError, Exception):
            return e.code, None
    except (URLError, TimeoutError):
        return 0, None


class Verifier:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        ok = bool(condition)
        if ok:
            self.passed += 1
            self.results.append((name, True, detail or "OK"))
        else:
            self.failed += 1
            self.results.append((name, False, detail or "assertion failed"))

    def print_summary(self):
        for name, ok, detail in self.results:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}: {detail}")
        total = self.passed + self.failed
        print(f"\n{'=' * 60}")
        print(f"  {self.passed}/{total} passed, {self.failed} failed")
        if self.failed:
            print("  VERDICT: FAIL", file=sys.stderr)
        else:
            print("  VERDICT: PASS")


def check_d004(v: Verifier, prefix: str, body: dict):
    missing = D004_REQUIRED - set(body.keys())
    v.check(f"{prefix} D004 fields present", not missing,
            f"missing={sorted(missing)}" if missing else "source/data_status/mock present")
    ds = body.get("data_status")
    v.check(f"{prefix} data_status valid", ds in ALLOWED_STATUS,
            f"data_status={ds!r}")
    mock = body.get("mock")
    v.check(f"{prefix} mock is bool", isinstance(mock, bool),
            f"mock={mock!r} type={type(mock).__name__}")
    if mock and ds != "mock":
        v.check(f"{prefix} D004 consistency", False,
                f"mock=True but data_status={ds!r}")
    elif ds == "mock" and not mock:
        v.check(f"{prefix} D004 consistency", False,
                f"data_status='mock' but mock=False")


def test_screen_normal(v: Verifier):
    """GET /value/screen?max_pe=15&min_roe=20 — real data when TuShare has data."""
    print("\n--- /value/screen (normal filters) ---")
    status, body = get("/api/value/screen?max_pe=15&min_roe=20")
    v.check("screen-normal HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("screen-normal has body", False, "empty response")
        return
    check_d004(v, "screen-normal", body)
    v.check("screen-normal source=tushare",
            body.get("source") == "tushare",
            f"source={body.get('source')!r}")
    ds = body.get("data_status")
    v.check("screen-normal data_status real|empty",
            ds in ("real", "empty"),
            f"data_status={ds!r} (empty is valid when TuShare returns no data)")
    v.check("screen-normal mock=False",
            body.get("mock") is False,
            f"mock={body.get('mock')!r}")
    count = body.get("count", 0)
    if ds == "real":
        v.check("screen-normal ≥1 results when real",
                count >= 1,
                f"count={count}")
    else:
        print(f"  [INFO] screen returned empty (count=0) — TuShare data not available (weekend/holiday/rate-limit)")


def test_screen_extreme(v: Verifier):
    """GET /value/screen with extreme filters — expect real/empty, never mock."""
    print("\n--- /value/screen (extreme filters) ---")
    status, body = get("/api/value/screen?max_pe=5&min_roe=50")
    v.check("screen-extreme HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("screen-extreme has body", False, "empty response")
        return
    check_d004(v, "screen-extreme", body)
    ds = body.get("data_status")
    v.check("screen-extreme status real|empty",
            ds in ("real", "empty"),
            f"data_status={ds!r}")
    v.check("screen-extreme mock=False",
            body.get("mock") is False,
            f"mock={body.get('mock')!r}")


def test_financial_known(v: Verifier, code: str, label: str):
    """GET /value/financial/{code} — known stock, expect real data."""
    print(f"\n--- /value/financial/{code} ({label}) ---")
    status, body = get(f"/api/value/financial/{code}")
    v.check(f"fin-{code} HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check(f"fin-{code} has body", False, "empty response")
        return
    check_d004(v, f"fin-{code}", body)
    ds = body.get("data_status")
    v.check(f"fin-{code} data_status=real",
            ds == "real",
            f"data_status={ds!r}")
    src = body.get("source")
    v.check(f"fin-{code} source dfcf|tushare",
            src in ("dfcf", "tushare"),
            f"source={src!r}")
    v.check(f"fin-{code} mock=False",
            body.get("mock") is False,
            f"mock={body.get('mock')!r}")
    data = body.get("data", {})
    if isinstance(data, dict):
        v.check(f"fin-{code} has pe", "pe" in data, f"keys={sorted(data.keys())[:10]}")
        v.check(f"fin-{code} has name", bool(data.get("name")), f"name={data.get('name')!r}")


def test_financial_invalid(v: Verifier):
    """GET /value/financial/999999 — nonexistent stock, expect unavailable (not mock)."""
    print("\n--- /value/financial/999999 (invalid) ---")
    status, body = get("/api/value/financial/999999")
    v.check("fin-999999 HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("fin-999999 has body", False, "empty response")
        return
    check_d004(v, "fin-999999", body)
    ds = body.get("data_status")
    v.check("fin-999999 status unavailable|empty",
            ds in ("unavailable", "empty"),
            f"data_status={ds!r}")
    v.check("fin-999999 mock=False",
            body.get("mock") is False,
            f"mock={body.get('mock')!r}")


def main() -> int:
    print(f"S01 Value Endpoints Verification")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()
    test_screen_normal(v)
    test_screen_extreme(v)
    test_financial_known(v, "000001", "平安银行")
    test_financial_known(v, "600519", "贵州茅台")
    test_financial_invalid(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
