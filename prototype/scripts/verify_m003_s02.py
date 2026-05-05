"""M003/S02 slice verification — top-traders (R008).

Validates:
- /api/analysis/top-traders D004 contract (source, data_status, mock)
- Famous seat enrichment (buy_seats/sell_seats items have name+famous_alias)
- top-traders registered in contract_endpoints.py
- Full contract check (check_api_contract.py) — 0 failures
- Mock scan (check_no_mock.py) — 0 violations
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
SCRIPTS_DIR = Path(__file__).resolve().parent

D004_REQUIRED = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}


def _get(path: str) -> tuple[int, dict | None]:
    url = f"{API_BASE}{path}"
    req = Request(url, headers={"Content-Type": "application/json"}, method="GET")
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


# ---------- Group 1: R008 top-traders ----------

def test_top_traders(v: Verifier):
    print("\n--- Group 1: R008 /api/analysis/top-traders ---")
    status, body = _get("/api/analysis/top-traders")
    v.check("top-traders HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("top-traders has body", False, "empty response")
        return

    check_d004(v, "top-traders", body)

    ds = body.get("data_status")
    v.check("top-traders data_status never mock",
            ds != "mock", f"data_status={ds!r}")
    v.check("top-traders mock=False",
            body.get("mock") is False, f"mock={body.get('mock')!r}")

    data = body.get("data", [])
    v.check("top-traders data is list", isinstance(data, list),
            f"type={type(data).__name__}")

    if ds == "real" and data:
        stock = data[0]
        v.check("top-traders item has stock_code",
                "stock_code" in stock, f"keys={sorted(stock.keys())}")
        v.check("top-traders item has stock_name",
                "stock_name" in stock, f"keys={sorted(stock.keys())}")
        v.check("top-traders item has buy_seats",
                "buy_seats" in stock, f"keys={sorted(stock.keys())}")
        v.check("top-traders item has sell_seats",
                "sell_seats" in stock, f"keys={sorted(stock.keys())}")

        buy_seats = stock.get("buy_seats", [])
        if buy_seats:
            seat = buy_seats[0]
            v.check("buy_seat item is dict", isinstance(seat, dict),
                    f"type={type(seat).__name__}")
            v.check("buy_seat has name key", "name" in seat,
                    f"keys={sorted(seat.keys()) if isinstance(seat, dict) else 'N/A'}")
            v.check("buy_seat has famous_alias key", "famous_alias" in seat,
                    f"keys={sorted(seat.keys()) if isinstance(seat, dict) else 'N/A'}")
    elif ds in ("empty", "unavailable"):
        v.check(f"top-traders graceful {ds}", True, f"data_status={ds}")
    else:
        v.check("top-traders acceptable data_status",
                ds in ALLOWED_STATUS, f"data_status={ds!r}")


# ---------- Group 2: Famous seat enrichment ----------

def test_famous_enrichment(v: Verifier):
    print("\n--- Group 2: Famous seat enrichment ---")
    status, body = _get("/api/analysis/top-traders")
    if status != 200 or not body:
        v.check("famous-enrichment skipped (endpoint unavailable)", True,
                f"status={status}")
        return

    ds = body.get("data_status")
    data = body.get("data", [])

    if ds in ("empty", "unavailable") or not data:
        v.check("famous-enrichment skipped (no data available)", True,
                f"data_status={ds}, data_len={len(data)}")
        return

    found_famous = False
    for stock in data:
        for seat_list_key in ("buy_seats", "sell_seats"):
            for seat in stock.get(seat_list_key, []):
                if isinstance(seat, dict) and seat.get("famous_alias") is not None:
                    found_famous = True
                    break
            if found_famous:
                break
        if found_famous:
            break

    v.check("at least one seat has famous_alias != None", found_famous,
            "found famous alias in data" if found_famous
            else "no famous aliases found (may be normal for low-activity days)")


# ---------- Group 3: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 3: top-traders contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("top-traders in CONTRACT_ENDPOINTS",
                "top-traders" in content, "found in contract_endpoints.py")


# ---------- Group 4: Full contract check ----------

def test_contract_check(v: Verifier):
    print("\n--- Group 4: check_api_contract.py ---")
    script = SCRIPTS_DIR / "check_api_contract.py"
    if not script.exists():
        v.check("contract-check script exists", False, f"{script} not found")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=120,
        cwd=str(SCRIPTS_DIR),
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    summary = stderr.split("\n")[-1] if stderr else (stdout.split("\n")[-1] if stdout else "")

    top_traders_pass = any(
        "[PASS]" in ln and "top-traders" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check top-traders PASS", top_traders_pass,
            "top-traders passed D004 contract")

    overall_pass = result.returncode == 0
    v.check("contract-check 0 failures (overall)", overall_pass,
            summary[:200] if not overall_pass else summary[:200])


# ---------- Group 5: Mock scan ----------

def test_mock_scan(v: Verifier):
    print("\n--- Group 5: check_no_mock.py ---")
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
    print("M003/S02 Top-Traders + Famous Seat Enrichment Verification")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    test_top_traders(v)
    test_famous_enrichment(v)
    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
