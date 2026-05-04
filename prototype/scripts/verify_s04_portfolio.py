"""S04 slice verification — exercises portfolio flow end-to-end.

Tests: schema columns, watchlist CRUD with cost_price/shares, GET /growth/portfolio
with real DFCF live prices, D004 contract fields, empty/no-position edge cases.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DB_PATH = os.environ.get(
    "ZHICE_DB_PATH",
    str(Path(__file__).resolve().parents[1] / "data" / "zhice.db"),
)

D004_REQUIRED = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}

_TEST_PHONE = f"s04test_{uuid.uuid4().hex[:8]}"
_TEST_PASSWORD = "Test123456"
_TEST_INVITE = f"S4{uuid.uuid4().hex[:4].upper()}"
_TOKEN: str | None = None

_created_watchlist_ids: list[int] = []


# ---------- HTTP helpers ----------

def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if _TOKEN:
        headers["Authorization"] = f"Bearer {_TOKEN}"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as res:
            return res.status, json.loads(res.read().decode())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, None
    except (URLError, TimeoutError):
        return 0, None


def get(path: str) -> tuple[int, dict | None]:
    return _req("GET", path)


def post(path: str, body: dict) -> tuple[int, dict | None]:
    return _req("POST", path, body)


def patch(path: str, body: dict) -> tuple[int, dict | None]:
    return _req("PATCH", path, body)


def delete(path: str) -> tuple[int, dict | None]:
    return _req("DELETE", path)


# ---------- Verifier ----------

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


# ---------- Auth setup ----------

def setup_auth() -> bool:
    """Register a test user via DB invite code injection + API registration."""
    global _TOKEN
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, max_uses, used_count) VALUES (?, 10, 0)",
            (_TEST_INVITE,),
        )
        conn.commit()
    finally:
        conn.close()

    status, body = post("/api/auth/register", {
        "phone": _TEST_PHONE,
        "password": _TEST_PASSWORD,
        "nickname": "S04Test",
        "invite_code": _TEST_INVITE,
        "terms_accepted": True,
    })
    if status == 200 and body and "token" in body:
        _TOKEN = body["token"]
        return True

    status, body = post("/api/auth/login", {
        "phone": _TEST_PHONE,
        "password": _TEST_PASSWORD,
    })
    if status == 200 and body and "token" in body:
        _TOKEN = body["token"]
        return True
    return False


def cleanup_auth():
    """Remove test user, invite code, and any leftover watchlist entries."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("DELETE FROM invite_codes WHERE code=?", (_TEST_INVITE,))
        conn.execute("DELETE FROM watchlist WHERE user_id IN (SELECT id FROM users WHERE phone=?)", (_TEST_PHONE,))
        conn.execute("DELETE FROM users WHERE phone=?", (_TEST_PHONE,))
        conn.commit()
    finally:
        conn.close()


# ---------- Test Group 1: Schema ----------

def test_schema(v: Verifier):
    print("\n--- Group 1: Schema Validation ---")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(watchlist)").fetchall()}
    finally:
        conn.close()
    v.check("schema cost_price column exists", "cost_price" in cols,
            f"columns={sorted(cols)}")
    v.check("schema shares column exists", "shares" in cols,
            f"columns={sorted(cols)}")


# ---------- Test Group 2: CRUD with cost_price/shares ----------

def test_crud(v: Verifier):
    print("\n--- Group 2: Watchlist CRUD with cost_price/shares ---")
    status, body = post("/api/watchlist", {
        "code": "600519",
        "name": "贵州茅台",
        "cost_price": 1800.0,
        "shares": 100,
    })
    v.check("crud POST 200", status == 200, f"status={status}")
    v.check("crud POST ok", body and body.get("ok") is True, f"body={body}")
    wid = body.get("id") if body else None
    if wid:
        _created_watchlist_ids.append(wid)

    if not wid:
        v.check("crud POST returned id", False, "no id in response, skipping rest of CRUD")
        return

    status2, body2 = patch(f"/api/watchlist/{wid}", {"cost_price": 1850.0})
    v.check("crud PATCH 200", status2 == 200, f"status={status2}")
    v.check("crud PATCH ok", body2 and body2.get("ok") is True, f"body={body2}")

    status3, _ = delete(f"/api/watchlist/{wid}")
    v.check("crud DELETE 200", status3 == 200, f"status={status3}")
    if wid in _created_watchlist_ids:
        _created_watchlist_ids.remove(wid)


# ---------- Test Group 3: Portfolio endpoint with real data ----------

def test_portfolio_real(v: Verifier):
    print("\n--- Group 3: Portfolio with real DFCF prices ---")
    status_add, body_add = post("/api/watchlist", {
        "code": "600519",
        "name": "贵州茅台",
        "cost_price": 1800.0,
        "shares": 100,
    })
    wid = body_add.get("id") if body_add else None
    if wid:
        _created_watchlist_ids.append(wid)

    if not wid:
        v.check("portfolio-real setup", False, "failed to add test position")
        return

    time.sleep(0.5)

    status, body = get("/api/growth/portfolio")
    v.check("portfolio HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("portfolio has body", False, "empty response")
        _cleanup_watchlist_ids()
        return

    check_d004(v, "portfolio", body)

    v.check("portfolio mock=False", body.get("mock") is False,
            f"mock={body.get('mock')!r}")

    ds = body.get("data_status")
    v.check("portfolio status real|unavailable",
            ds in ("real", "unavailable"),
            f"data_status={ds!r} (unavailable ok if market closed)")

    src = body.get("source")
    v.check("portfolio source=dfcf", src == "dfcf",
            f"source={src!r}")

    stocks = body.get("stocks", [])
    v.check("portfolio has stocks array", isinstance(stocks, list) and len(stocks) >= 1,
            f"len(stocks)={len(stocks) if isinstance(stocks, list) else 'not-a-list'}")

    if stocks:
        s = stocks[0]
        v.check("portfolio stock has code", s.get("code") == "600519",
                f"code={s.get('code')!r}")
        v.check("portfolio stock has cost_price", s.get("cost_price") == 1800.0,
                f"cost_price={s.get('cost_price')!r}")
        v.check("portfolio stock has shares", s.get("shares") == 100,
                f"shares={s.get('shares')!r}")
        v.check("portfolio stock has current_price field", "current_price" in s,
                f"keys={sorted(s.keys())}")
        v.check("portfolio stock has market_value field", "market_value" in s,
                f"keys={sorted(s.keys())}")
        v.check("portfolio stock has pnl field", "pnl" in s,
                f"keys={sorted(s.keys())}")
        v.check("portfolio stock has pnl_rate field", "pnl_rate" in s,
                f"keys={sorted(s.keys())}")

        cp = s.get("current_price")
        if cp is not None and isinstance(cp, (int, float)) and cp > 0:
            expected_mv = round(cp * 100, 2)
            actual_mv = s.get("market_value")
            v.check("portfolio pnl calc: market_value = price*shares",
                    actual_mv is not None and abs(actual_mv - expected_mv) < 0.1,
                    f"expected~{expected_mv}, got={actual_mv}")
            expected_pnl = round(expected_mv - 1800.0 * 100, 2)
            actual_pnl = s.get("pnl")
            v.check("portfolio pnl calc: pnl = mv - cost_basis",
                    actual_pnl is not None and abs(actual_pnl - expected_pnl) < 1.0,
                    f"expected~{expected_pnl}, got={actual_pnl}")
        else:
            print(f"  [INFO] current_price={cp!r} — market may be closed, skipping PnL math checks")

    v.check("portfolio has total_value", "total_value" in body,
            f"total_value={body.get('total_value', 'MISSING')}")
    v.check("portfolio has total_pnl", "total_pnl" in body,
            f"total_pnl={body.get('total_pnl', 'MISSING')}")
    v.check("portfolio has total_pnl_rate", "total_pnl_rate" in body,
            f"total_pnl_rate={body.get('total_pnl_rate', 'MISSING')}")

    _cleanup_watchlist_ids()


# ---------- Test Group 4: Empty portfolio ----------

def test_portfolio_empty(v: Verifier):
    print("\n--- Group 4: Empty portfolio ---")
    status, body = get("/api/growth/portfolio")
    v.check("empty-portfolio HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("empty-portfolio has body", False, "empty response")
        return
    check_d004(v, "empty-portfolio", body)
    ds = body.get("data_status")
    v.check("empty-portfolio status=empty", ds == "empty",
            f"data_status={ds!r}")
    v.check("empty-portfolio mock=False", body.get("mock") is False,
            f"mock={body.get('mock')!r}")
    stocks = body.get("stocks", [])
    v.check("empty-portfolio stocks empty", isinstance(stocks, list) and len(stocks) == 0,
            f"len(stocks)={len(stocks) if isinstance(stocks, list) else 'not-list'}")


# ---------- Test Group 5: Watchlist items without cost_price ----------

def test_no_cost_price_excluded(v: Verifier):
    print("\n--- Group 5: Items without cost_price excluded ---")
    status_add, body_add = post("/api/watchlist", {
        "code": "000001",
        "name": "平安银行",
    })
    wid = body_add.get("id") if body_add else None
    if wid:
        _created_watchlist_ids.append(wid)

    if not wid:
        v.check("no-cost setup", False, "failed to add watchlist item without cost_price")
        return

    time.sleep(0.3)

    status, body = get("/api/growth/portfolio")
    v.check("no-cost portfolio HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("no-cost portfolio has body", False, "empty response")
        _cleanup_watchlist_ids()
        return

    ds = body.get("data_status")
    stocks = body.get("stocks", [])
    codes_in_portfolio = [s.get("code") for s in stocks] if isinstance(stocks, list) else []
    v.check("no-cost item excluded from portfolio",
            "000001" not in codes_in_portfolio,
            f"codes_in_portfolio={codes_in_portfolio}")
    v.check("no-cost portfolio status=empty",
            ds == "empty",
            f"data_status={ds!r} (only no-cost items exist, so portfolio should be empty)")

    _cleanup_watchlist_ids()


# ---------- Cleanup helpers ----------

def _cleanup_watchlist_ids():
    for wid in list(_created_watchlist_ids):
        try:
            delete(f"/api/watchlist/{wid}")
        except Exception:
            pass
    _created_watchlist_ids.clear()


# ---------- Main ----------

def main() -> int:
    print("S04 Portfolio End-to-End Verification")
    print(f"Target: {API_BASE}")
    print(f"DB: {DB_PATH}")
    print("=" * 60)

    v = Verifier()

    test_schema(v)

    if not setup_auth():
        print("  [FATAL] Could not authenticate — skipping API tests")
        v.check("auth setup", False, "registration/login failed")
        v.print_summary()
        return 1

    try:
        test_portfolio_empty(v)
        test_crud(v)
        test_portfolio_real(v)
        test_no_cost_price_excluded(v)
    finally:
        _cleanup_watchlist_ids()
        cleanup_auth()

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
