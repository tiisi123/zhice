"""M003/S05 slice verification — Backtest endpoints (R011, R012).

Validates:
- GET /api/backtest/board-strategy returns HTTP 200 + D004 fields
- Board-strategy response schema: strategy_name, total_return, annualized_return,
  max_drawdown, sharpe_ratio, win_rate, profit_loss_ratio, max_consecutive_loss,
  total_trades, equity_curve (list), trade_log (list)
- Board-strategy sub-strategy variants (首板, 二板, 龙头) all return 200
- Board-strategy determinism (identical sample calls return identical results)
- Board-strategy invalid sub_strategy returns 400
- GET /api/backtest/etf-rotation returns HTTP 200 + D004 fields
- ETF-rotation schema: strategy_name, total_return, annualized_return,
  max_drawdown, sharpe_ratio, equity_curve, rebalance_log, etf_count=13
- ETF-rotation determinism
- Contract registration: both endpoints in contract_endpoints.py
- check_api_contract.py passes
- check_no_mock.py: 0 violations
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
SCRIPTS_DIR = Path(__file__).resolve().parent

D004_REQUIRED = {"source", "data_status", "mock"}
ALLOWED_STATUS = {"real", "mock", "fallback", "unavailable", "empty", "error"}

BOARD_REQUIRED_FIELDS = {
    "strategy_name", "total_return", "annualized_return", "max_drawdown",
    "sharpe_ratio", "win_rate", "profit_loss_ratio", "max_consecutive_loss",
    "total_trades", "equity_curve", "trade_log",
}

ETF_REQUIRED_FIELDS = {
    "strategy_name", "total_return", "annualized_return", "max_drawdown",
    "sharpe_ratio", "equity_curve", "rebalance_log", "etf_count",
}


def _get(path: str) -> tuple[int, dict | None]:
    url = f"{API_BASE}{quote(path, safe='/:?=&')}"
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


# ---------- Group 1: Board-strategy HTTP 200 + D004 ----------

def test_board_http_200_d004(v: Verifier) -> dict | None:
    print("\n--- Group 1: Board-strategy HTTP 200 + D004 (mode=sample) ---")
    status, body = _get("/api/backtest/board-strategy?mode=sample")
    v.check("board-strategy HTTP 200", status == 200, f"status={status}")
    v.check("board-strategy has body", body is not None, "non-null response")
    if body:
        check_d004(v, "board-strategy", body)
        src = body.get("source")
        v.check("board-strategy source non-empty",
                isinstance(src, str) and len(src) > 0, f"source={src!r}")
    return body


# ---------- Group 2: Board-strategy response schema ----------

def test_board_schema(v: Verifier, body: dict):
    print("\n--- Group 2: Board-strategy response schema ---")
    data = body.get("data", {})
    if not isinstance(data, dict):
        v.check("board-strategy data is dict", False, f"type={type(data).__name__}")
        return

    missing = BOARD_REQUIRED_FIELDS - set(data.keys())
    v.check("board-strategy has all required fields", not missing,
            f"missing={sorted(missing)}" if missing else "all 11 fields present")

    v.check("board-strategy equity_curve is list",
            isinstance(data.get("equity_curve"), list),
            f"type={type(data.get('equity_curve')).__name__}")
    v.check("board-strategy trade_log is list",
            isinstance(data.get("trade_log"), list),
            f"type={type(data.get('trade_log')).__name__}")
    v.check("board-strategy total_return is numeric",
            isinstance(data.get("total_return"), (int, float)),
            f"total_return={data.get('total_return')!r}")
    v.check("board-strategy sharpe_ratio is numeric",
            isinstance(data.get("sharpe_ratio"), (int, float)),
            f"sharpe_ratio={data.get('sharpe_ratio')!r}")
    v.check("board-strategy win_rate is numeric (R012)",
            isinstance(data.get("win_rate"), (int, float)),
            f"win_rate={data.get('win_rate')!r}")
    v.check("board-strategy profit_loss_ratio is numeric (R012)",
            isinstance(data.get("profit_loss_ratio"), (int, float)),
            f"profit_loss_ratio={data.get('profit_loss_ratio')!r}")
    v.check("board-strategy max_consecutive_loss is int (R012)",
            isinstance(data.get("max_consecutive_loss"), int),
            f"max_consecutive_loss={data.get('max_consecutive_loss')!r}")


# ---------- Group 3: Board-strategy sub-strategy variants ----------

def test_board_sub_strategies(v: Verifier):
    print("\n--- Group 3: Board-strategy sub-strategy variants ---")
    for sub in ("首板", "二板", "龙头"):
        status, body = _get(f"/api/backtest/board-strategy?mode=sample&sub_strategy={sub}")
        v.check(f"board-strategy sub={sub} HTTP 200", status == 200,
                f"status={status}")
        if body and isinstance(body.get("data"), dict):
            sn = body["data"].get("strategy_name", "")
            v.check(f"board-strategy sub={sub} has strategy_name",
                    isinstance(sn, str) and len(sn) > 0, f"strategy_name={sn!r}")


# ---------- Group 4: Board-strategy determinism ----------

def test_board_determinism(v: Verifier):
    print("\n--- Group 4: Board-strategy determinism (mode=sample) ---")
    _, body1 = _get("/api/backtest/board-strategy?mode=sample&sub_strategy=首板")
    _, body2 = _get("/api/backtest/board-strategy?mode=sample&sub_strategy=首板")
    if not body1 or not body2:
        v.check("board determinism both calls returned data", False,
                "one or both calls failed")
        return
    d1 = body1.get("data", {})
    d2 = body2.get("data", {})
    v.check("board determinism total_return matches",
            d1.get("total_return") == d2.get("total_return"),
            f"call1={d1.get('total_return')} call2={d2.get('total_return')}")
    v.check("board determinism total_trades matches",
            d1.get("total_trades") == d2.get("total_trades"),
            f"call1={d1.get('total_trades')} call2={d2.get('total_trades')}")


# ---------- Group 5: Board-strategy invalid sub_strategy ----------

def test_board_invalid_sub(v: Verifier):
    print("\n--- Group 5: Board-strategy invalid sub_strategy ---")
    status, body = _get("/api/backtest/board-strategy?mode=sample&sub_strategy=invalid_xyz")
    v.check("board-strategy invalid sub returns 400/422",
            status in (400, 422), f"status={status}")


# ---------- Group 6: ETF-rotation HTTP 200 + D004 ----------

def test_etf_http_200_d004(v: Verifier) -> dict | None:
    print("\n--- Group 6: ETF-rotation HTTP 200 + D004 (mode=sample) ---")
    status, body = _get("/api/backtest/etf-rotation?mode=sample")
    v.check("etf-rotation HTTP 200", status == 200, f"status={status}")
    v.check("etf-rotation has body", body is not None, "non-null response")
    if body:
        check_d004(v, "etf-rotation", body)
        src = body.get("source")
        v.check("etf-rotation source non-empty",
                isinstance(src, str) and len(src) > 0, f"source={src!r}")
    return body


# ---------- Group 7: ETF-rotation response schema ----------

def test_etf_schema(v: Verifier, body: dict):
    print("\n--- Group 7: ETF-rotation response schema (R011) ---")
    data = body.get("data", {})
    if not isinstance(data, dict):
        v.check("etf-rotation data is dict", False, f"type={type(data).__name__}")
        return

    missing = ETF_REQUIRED_FIELDS - set(data.keys())
    v.check("etf-rotation has all required fields", not missing,
            f"missing={sorted(missing)}" if missing else "all 8 fields present")

    v.check("etf-rotation equity_curve is list",
            isinstance(data.get("equity_curve"), list),
            f"type={type(data.get('equity_curve')).__name__}")
    v.check("etf-rotation rebalance_log is list",
            isinstance(data.get("rebalance_log"), list),
            f"type={type(data.get('rebalance_log')).__name__}")
    v.check("etf-rotation etf_count == 13",
            data.get("etf_count") == 13,
            f"etf_count={data.get('etf_count')!r}")
    v.check("etf-rotation total_return is numeric (R011)",
            isinstance(data.get("total_return"), (int, float)),
            f"total_return={data.get('total_return')!r}")
    v.check("etf-rotation sharpe_ratio is numeric (R011)",
            isinstance(data.get("sharpe_ratio"), (int, float)),
            f"sharpe_ratio={data.get('sharpe_ratio')!r}")


# ---------- Group 8: ETF-rotation determinism ----------

def test_etf_determinism(v: Verifier):
    print("\n--- Group 8: ETF-rotation determinism (mode=sample) ---")
    _, body1 = _get("/api/backtest/etf-rotation?mode=sample")
    _, body2 = _get("/api/backtest/etf-rotation?mode=sample")
    if not body1 or not body2:
        v.check("etf determinism both calls returned data", False,
                "one or both calls failed")
        return
    d1 = body1.get("data", {})
    d2 = body2.get("data", {})
    v.check("etf determinism total_return matches",
            d1.get("total_return") == d2.get("total_return"),
            f"call1={d1.get('total_return')} call2={d2.get('total_return')}")
    v.check("etf determinism total_trades matches",
            d1.get("total_trades") == d2.get("total_trades"),
            f"call1={d1.get('total_trades')} call2={d2.get('total_trades')}")


# ---------- Group 9: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 9: Backtest contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("board-strategy in CONTRACT_ENDPOINTS",
                "backtest/board-strategy" in content,
                "found in contract_endpoints.py")
        v.check("etf-rotation in CONTRACT_ENDPOINTS",
                "backtest/etf-rotation" in content,
                "found in contract_endpoints.py")


# ---------- Group 10: Full contract check ----------

def test_contract_check(v: Verifier):
    print("\n--- Group 10: check_api_contract.py ---")
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

    board_pass = any(
        "[PASS]" in ln and "board-strategy" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check board-strategy PASS", board_pass,
            "board-strategy passed D004 contract")

    etf_pass = any(
        "[PASS]" in ln and "etf-rotation" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check etf-rotation PASS", etf_pass,
            "etf-rotation passed D004 contract")

    overall_pass = result.returncode == 0
    v.check("contract-check 0 failures (overall)", overall_pass,
            summary[:200] if not overall_pass else summary[:200])


# ---------- Group 11: Mock scan ----------

def test_mock_scan(v: Verifier):
    print("\n--- Group 11: check_no_mock.py ---")
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
    print("M003/S05 Backtest Endpoints Verification (R011, R012)")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    board_body = test_board_http_200_d004(v)
    if not board_body:
        v.print_summary()
        return 1
    test_board_schema(v, board_body)
    test_board_sub_strategies(v)
    test_board_determinism(v)
    test_board_invalid_sub(v)

    etf_body = test_etf_http_200_d004(v)
    if not etf_body:
        v.print_summary()
        return 1
    test_etf_schema(v, etf_body)
    test_etf_determinism(v)

    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
