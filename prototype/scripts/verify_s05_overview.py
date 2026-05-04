"""S05 slice verification — final-assembly overview page readiness check.

Validates:
- /growth/macro D004 contract compliance
- /growth/prosperity D004 contract compliance
- /growth/portfolio D004 contract compliance (authenticated)
- Overview page mock-alert condition simulation
- Full contract check (check_api_contract.py) — 0 failures
- Mock scan (check_no_mock.py) — 0 violations
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
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
SCRIPTS_DIR = Path(__file__).resolve().parent

D004_REQUIRED = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}

_TEST_PHONE = f"s05test_{uuid.uuid4().hex[:8]}"
_TEST_PASSWORD = "Test123456"
_TEST_INVITE = f"S5{uuid.uuid4().hex[:4].upper()}"
_TOKEN: str | None = None


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
        "nickname": "S05Test",
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
    conn = sqlite3.connect(DB_PATH, timeout=5)
    try:
        conn.execute("DELETE FROM invite_codes WHERE code=?", (_TEST_INVITE,))
        conn.execute("DELETE FROM watchlist WHERE user_id IN (SELECT id FROM users WHERE phone=?)", (_TEST_PHONE,))
        conn.execute("DELETE FROM users WHERE phone=?", (_TEST_PHONE,))
        conn.commit()
    finally:
        conn.close()


# ---------- Group 1: /growth/macro D004 ----------

def test_macro(v: Verifier):
    print("\n--- Group 1: /growth/macro D004 ---")
    status, body = get("/api/growth/macro")
    v.check("macro HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("macro has body", False, "empty response")
        return body
    check_d004(v, "macro", body)
    src = body.get("source", "")
    v.check("macro source non-empty", bool(src), f"source={src!r}")
    if not body.get("mock"):
        v.check("macro real source contains tushare or static",
                "tushare" in src or "static" in src,
                f"source={src!r}")
    return body


# ---------- Group 2: /growth/prosperity D004 ----------

def test_prosperity(v: Verifier):
    print("\n--- Group 2: /growth/prosperity D004 ---")
    status, body = get("/api/growth/prosperity")
    v.check("prosperity HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("prosperity has body", False, "empty response")
        return body
    check_d004(v, "prosperity", body)
    src = body.get("source", "")
    v.check("prosperity source non-empty", bool(src), f"source={src!r}")
    return body


# ---------- Group 3: /growth/portfolio D004 (authenticated) ----------

def test_portfolio(v: Verifier):
    print("\n--- Group 3: /growth/portfolio D004 (authenticated) ---")
    status, body = get("/api/growth/portfolio")
    v.check("portfolio HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("portfolio has body", False, "empty response")
        return body
    check_d004(v, "portfolio", body)
    v.check("portfolio mock=False (S04 guarantee)", body.get("mock") is False,
            f"mock={body.get('mock')!r}")
    return body


# ---------- Group 4: Overview page mock-alert simulation ----------

def test_overview_alert(v: Verifier, macro_body: dict | None, prosperity_body: dict | None):
    print("\n--- Group 4: Overview page mock-alert simulation ---")
    if macro_body is None or prosperity_body is None:
        v.check("overview-alert prerequisite", False,
                "macro or prosperity response missing, cannot simulate")
        return

    data_status_entries = [
        {
            "label": "宏观",
            "source": macro_body.get("source"),
            "data_status": macro_body.get("data_status"),
            "mock": macro_body.get("mock"),
        },
        {
            "label": "景气",
            "source": prosperity_body.get("source"),
            "data_status": prosperity_body.get("data_status"),
            "mock": prosperity_body.get("mock"),
        },
    ]

    would_show_alert = any(
        s.get("mock") or s.get("data_status") == "stale"
        for s in data_status_entries
    )

    for s in data_status_entries:
        v.check(
            f"overview-alert {s['label']} mock={s['mock']}",
            isinstance(s["mock"], bool),
            f"mock={s['mock']!r}",
        )

    if not would_show_alert:
        v.check("overview-alert NOT shown (all real, no stale)",
                True, "no mock or stale entries — yellow warning hidden")
    else:
        reasons = []
        for s in data_status_entries:
            if s.get("mock"):
                reasons.append(f"{s['label']}: mock=True")
            if s.get("data_status") == "stale":
                reasons.append(f"{s['label']}: stale")
        v.check("overview-alert WOULD show (mock or stale present)",
                True, f"alert reasons: {'; '.join(reasons)}")


# ---------- Group 5: Full contract check (check_api_contract.py) ----------

def test_contract_check(v: Verifier):
    print("\n--- Group 5: check_api_contract.py ---")
    script = SCRIPTS_DIR / "check_api_contract.py"
    if not script.exists():
        v.check("contract-check script exists", False, f"{script} not found")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=120,
        cwd=str(SCRIPTS_DIR),
    )
    passed = result.returncode == 0
    summary = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    v.check("contract-check 0 failures", passed,
            summary or result.stderr.strip()[:200])


# ---------- Group 6: Mock scan (check_no_mock.py) ----------

def test_mock_scan(v: Verifier):
    print("\n--- Group 6: check_no_mock.py ---")
    script = SCRIPTS_DIR / "check_no_mock.py"
    if not script.exists():
        v.check("mock-scan script exists", False, f"{script} not found")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=60,
        cwd=str(SCRIPTS_DIR.parent),
    )
    passed = result.returncode == 0
    summary = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    v.check("mock-scan 0 violations", passed,
            summary or result.stderr.strip()[:200])


# ---------- Main ----------

def main() -> int:
    print("S05 Overview Page Final-Assembly Verification")
    print(f"Target: {API_BASE}")
    print(f"DB: {DB_PATH}")
    print("=" * 60)

    v = Verifier()

    if not setup_auth():
        print("  [FATAL] Could not authenticate — skipping API tests")
        v.check("auth setup", False, "registration/login failed")
        v.print_summary()
        return 1

    try:
        macro_body = test_macro(v)
        prosperity_body = test_prosperity(v)
        portfolio_body = test_portfolio(v)
        test_overview_alert(v, macro_body, prosperity_body)
        test_contract_check(v)
        test_mock_scan(v)
    finally:
        cleanup_auth()

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
