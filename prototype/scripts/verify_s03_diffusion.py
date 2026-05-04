"""S03 slice verification — exercises /value/diffusion, /value/turning-points, /value/weekly-report.

Tests D004 contract fields (source, data_status, mock) and validates that
source/status/mock dynamically reflect whether get_industry_prosperity()
returned real TuShare data or static fallback.
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


def check_source_coherence(v: Verifier, prefix: str, body: dict):
    """Verify source string reflects actual data origin."""
    src = body.get("source", "")
    ds = body.get("data_status")
    mock = body.get("mock")
    v.check(f"{prefix} source non-empty", bool(src), f"source={src!r}")
    if ds == "real":
        v.check(f"{prefix} real→tushare source", src.startswith("tushare"),
                f"source={src!r} (expected tushare+... when real)")
        v.check(f"{prefix} real→mock=False", mock is False,
                f"mock={mock!r}")
    elif ds == "mock":
        v.check(f"{prefix} mock→static source",
                "static_industry_prosperity" in src or src.startswith("static"),
                f"source={src!r} (expected static_industry_prosperity+... when mock)")
        v.check(f"{prefix} mock→mock=True", mock is True,
                f"mock={mock!r}")


def test_diffusion(v: Verifier):
    print("\n--- /value/diffusion ---")
    status, body = get("/api/value/diffusion")
    v.check("diffusion HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("diffusion has body", False, "empty response")
        return
    check_d004(v, "diffusion", body)
    check_source_coherence(v, "diffusion", body)
    ds = body.get("data_status")
    v.check("diffusion status real|mock", ds in ("real", "mock"),
            f"data_status={ds!r}")
    v.check("diffusion has diffusion_index",
            "diffusion_index" in body,
            f"keys={sorted(k for k in body.keys() if not k.startswith('_'))[:10]}")


def test_turning_points(v: Verifier):
    print("\n--- /value/turning-points ---")
    status, body = get("/api/value/turning-points")
    v.check("turning HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("turning has body", False, "empty response")
        return
    check_d004(v, "turning", body)
    ds = body.get("data_status")
    v.check("turning status real|mock|empty", ds in ("real", "mock", "empty"),
            f"data_status={ds!r}")
    if ds != "empty":
        check_source_coherence(v, "turning", body)
    else:
        v.check("turning empty→source non-empty",
                bool(body.get("source")),
                f"source={body.get('source')!r}")
    v.check("turning has count field", "count" in body,
            f"count={body.get('count', 'MISSING')}")


def test_weekly_report(v: Verifier):
    print("\n--- /value/weekly-report ---")
    status, body = get("/api/value/weekly-report")
    if status != 200:
        v.check("weekly-report HTTP 200", False,
                f"status={status} (LLM may be unavailable — not a D004 failure)")
        return
    v.check("weekly-report HTTP 200", True, f"status={status}")
    if not body:
        v.check("weekly-report has body", False, "empty response")
        return
    check_d004(v, "weekly-report", body)
    check_source_coherence(v, "weekly-report", body)
    ds = body.get("data_status")
    v.check("weekly-report status real|mock", ds in ("real", "mock"),
            f"data_status={ds!r}")
    src = body.get("source", "")
    v.check("weekly-report source has +llm suffix", "+llm" in src,
            f"source={src!r}")


def main() -> int:
    print("S03 Diffusion/TurningPoints/WeeklyReport Verification")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()
    test_diffusion(v)
    test_turning_points(v)
    test_weekly_report(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
