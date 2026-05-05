"""M003/S01 slice verification — board-replay (R006) + ladder enhancement (R007).

Validates:
- /api/analysis/board-replay D004 contract (first_board/consecutive/broken classification)
- /api/market/ladder D004 contract + tier_stats (promotion_rate, top_sectors)
- board-replay registered in contract_endpoints.py
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
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "prototype" / "scripts"

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


# ---------- Group 1: R006 board-replay ----------

def test_board_replay(v: Verifier):
    print("\n--- Group 1: R006 /api/analysis/board-replay ---")
    status, body = _get("/api/analysis/board-replay")
    v.check("board-replay HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("board-replay has body", False, "empty response")
        return

    check_d004(v, "board-replay", body)

    ds = body.get("data_status")
    v.check("board-replay data_status never mock",
            ds != "mock", f"data_status={ds!r}")
    v.check("board-replay mock=False",
            body.get("mock") is False, f"mock={body.get('mock')!r}")

    if ds == "real":
        data = body.get("data", body)
        v.check("board-replay has first_board key",
                "first_board" in data, f"keys={sorted(data.keys())[:10]}")
        v.check("board-replay has consecutive key",
                "consecutive" in data, f"keys={sorted(data.keys())[:10]}")
        v.check("board-replay has broken key",
                "broken" in data, f"keys={sorted(data.keys())[:10]}")

        fb = data.get("first_board", [])
        if fb:
            stock = fb[0]
            v.check("board-replay stock has stock_code",
                    "stock_code" in stock, f"keys={sorted(stock.keys())}")
            v.check("board-replay stock has stock_name",
                    "stock_name" in stock, f"keys={sorted(stock.keys())}")
            v.check("board-replay stock has seal_amount",
                    "seal_amount" in stock, f"keys={sorted(stock.keys())}")
            v.check("board-replay stock has sectors",
                    "sectors" in stock, f"keys={sorted(stock.keys())}")
    elif ds in ("empty", "unavailable"):
        v.check(f"board-replay graceful {ds}", True, f"data_status={ds}")
    else:
        v.check("board-replay acceptable data_status",
                ds in ALLOWED_STATUS, f"data_status={ds!r}")


# ---------- Group 2: R007 ladder enhancement ----------

def test_ladder(v: Verifier):
    print("\n--- Group 2: R007 /api/market/ladder ---")
    status, body = _get("/api/market/ladder")
    v.check("ladder HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("ladder has body", False, "empty response")
        return

    check_d004(v, "ladder", body)

    ds = body.get("data_status")

    has_tiers = "tiers" in body
    v.check("ladder has tiers field", has_tiers,
            f"tiers present={has_tiers}")

    has_tier_stats = "tier_stats" in body
    v.check("ladder has tier_stats field", has_tier_stats,
            f"tier_stats present={has_tier_stats}")

    if has_tier_stats and body["tier_stats"]:
        ts = body["tier_stats"]
        v.check("ladder tier_stats is dict", isinstance(ts, dict),
                f"type={type(ts).__name__}")

        if isinstance(ts, dict) and ts:
            first_key = next(iter(ts))
            tier_entry = ts[first_key]
            v.check("tier_stats entry has promotion_rate key",
                    "promotion_rate" in tier_entry,
                    f"keys={sorted(tier_entry.keys())}")
            v.check("tier_stats entry has top_sectors key",
                    "top_sectors" in tier_entry,
                    f"keys={sorted(tier_entry.keys())}")

            pr = tier_entry.get("promotion_rate")
            v.check("tier_stats promotion_rate is number or None",
                    pr is None or isinstance(pr, (int, float)),
                    f"promotion_rate={pr!r} type={type(pr).__name__}")

            sectors = tier_entry.get("top_sectors")
            v.check("tier_stats top_sectors is list",
                    isinstance(sectors, list),
                    f"type={type(sectors).__name__}")
    elif ds in ("empty", "unavailable"):
        v.check(f"ladder graceful {ds} (tier_stats may be absent)", True,
                f"data_status={ds}")


# ---------- Group 3: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 3: board-replay contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("board-replay in CONTRACT_ENDPOINTS",
                "board-replay" in content, "found in contract_endpoints.py")


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

    board_replay_pass = any(
        "[PASS]" in ln and "board-replay" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check board-replay PASS", board_replay_pass,
            "board-replay passed D004 contract")

    ladder_pass = any(
        "[PASS]" in ln and "/api/market/ladder " in ln for ln in stdout.splitlines()
    )
    v.check("contract-check ladder PASS", ladder_pass,
            "ladder passed D004 contract")

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
    print("M003/S01 Board-Replay + Ladder Enhancement Verification")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    test_board_replay(v)
    test_ladder(v)
    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
