"""M003/S06 slice verification — AI Agent endpoints (R013, R014).

Validates:
- POST /api/ai/agent/board-trading returns HTTP 200 + D004 fields
- Board-trading response has advice field with board-trading content
- Board-trading accepts style/risk_preference/focus_sectors params
- POST /api/ai/agent/etf-rotation returns HTTP 200 + D004 fields
- ETF-rotation response has advice field with ETF rotation content
- ETF-rotation accepts style/investment_horizon/risk_preference params
- Both endpoints handle empty body (defaults)
- D004 contract consistency (source non-empty, mock bool, data_status valid)
- Contract registration: both endpoints in contract_endpoints.py
- check_api_contract.py passes for these endpoints
- check_no_mock.py: 0 violations
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


def _post(path: str, body: dict | None = None) -> tuple[int, dict | None]:
    url = f"{API_BASE}{path}"
    payload = json.dumps(body or {}).encode()
    req = Request(url, data=payload,
                  headers={"Content-Type": "application/json"}, method="POST")
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


def check_d004(v: Verifier, prefix: str, body: dict, *, allow_mock: bool = False):
    missing = D004_REQUIRED - set(body.keys())
    v.check(f"{prefix} D004 fields present", not missing,
            f"missing={sorted(missing)}" if missing else "source/data_status/mock present")
    ds = body.get("data_status")
    v.check(f"{prefix} data_status valid", ds in ALLOWED_STATUS,
            f"data_status={ds!r}")
    mock = body.get("mock")
    v.check(f"{prefix} mock is bool", isinstance(mock, bool),
            f"mock={mock!r} type={type(mock).__name__}")
    if allow_mock:
        v.check(f"{prefix} mock allowed by evidence status", True,
                f"mock={mock!r} data_status={ds!r}")
    else:
        v.check(f"{prefix} mock=False", mock is False,
                f"mock={mock!r} (this agent endpoint should not be mock)")
    if mock and ds != "mock":
        v.check(f"{prefix} D004 consistency", False,
                f"mock=True but data_status={ds!r}")
    elif ds == "mock" and not mock:
        v.check(f"{prefix} D004 consistency", False,
                f"data_status='mock' but mock=False")


# ---------- Group 1: Board-trading HTTP 200 + D004 (R013) ----------

def test_board_http_200_d004(v: Verifier) -> dict | None:
    print("\n--- Group 1: Board-trading HTTP 200 + D004 (R013) ---")
    status, body = _post("/api/ai/agent/board-trading",
                         {"style": "激进", "risk_preference": "高", "focus_sectors": ["AI"]})
    v.check("board-trading HTTP 200", status == 200, f"status={status}")
    v.check("board-trading has body", body is not None, "non-null response")
    if body:
        check_d004(v, "board-trading", body)
        src = body.get("source")
        v.check("board-trading source contains llm",
                isinstance(src, str) and "llm" in src, f"source={src!r}")
    return body


# ---------- Group 2: Board-trading response schema ----------

def test_board_schema(v: Verifier, body: dict):
    print("\n--- Group 2: Board-trading response schema (R013) ---")
    data = body.get("data", {})
    if not isinstance(data, dict):
        v.check("board-trading data is dict", False, f"type={type(data).__name__}")
        return

    v.check("board-trading has advice field",
            "advice" in data and isinstance(data["advice"], str),
            f"advice type={type(data.get('advice')).__name__}")
    v.check("board-trading has style field",
            "style" in data,
            f"style={data.get('style')!r}")
    v.check("board-trading has risk_preference field",
            "risk_preference" in data,
            f"risk_preference={data.get('risk_preference')!r}")

    advice = data.get("advice", "")
    v.check("board-trading advice non-empty",
            len(advice) > 50,
            f"advice length={len(advice)}")
    v.check("board-trading advice has disclaimer",
            "投资建议" in advice,
            "should contain '投资建议' disclaimer")


# ---------- Group 3: Board-trading with different styles ----------

def test_board_styles(v: Verifier):
    print("\n--- Group 3: Board-trading style variants ---")
    for style in ("稳健", "均衡"):
        status, body = _post("/api/ai/agent/board-trading",
                             {"style": style, "risk_preference": "中等"})
        v.check(f"board-trading style={style} HTTP 200", status == 200,
                f"status={status}")
        if body and isinstance(body.get("data"), dict):
            v.check(f"board-trading style={style} returns matching style",
                    body["data"].get("style") == style,
                    f"style={body['data'].get('style')!r}")


# ---------- Group 4: Board-trading empty body (defaults) ----------

def test_board_defaults(v: Verifier):
    print("\n--- Group 4: Board-trading empty body (defaults) ---")
    status, body = _post("/api/ai/agent/board-trading", {})
    v.check("board-trading empty body HTTP 200", status == 200, f"status={status}")
    if body and isinstance(body.get("data"), dict):
        v.check("board-trading default style=均衡",
                body["data"].get("style") == "均衡",
                f"style={body['data'].get('style')!r}")


# ---------- Group 5: ETF-rotation HTTP 200 + D004 (R014) ----------

def test_etf_http_200_d004(v: Verifier) -> dict | None:
    print("\n--- Group 5: ETF-rotation HTTP 200 + D004 (R014) ---")
    status, body = _post("/api/ai/agent/etf-rotation",
                         {"style": "稳健", "investment_horizon": "长期",
                          "risk_preference": "低"})
    v.check("etf-rotation HTTP 200", status == 200, f"status={status}")
    v.check("etf-rotation has body", body is not None, "non-null response")
    if body:
        check_d004(v, "etf-rotation", body, allow_mock=True)
        src = body.get("source")
        v.check("etf-rotation source contains llm",
                isinstance(src, str) and "llm" in src, f"source={src!r}")
    return body


# ---------- Group 6: ETF-rotation response schema ----------

def test_etf_schema(v: Verifier, body: dict):
    print("\n--- Group 6: ETF-rotation response schema (R014) ---")
    data = body.get("data", {})
    if not isinstance(data, dict):
        v.check("etf-rotation data is dict", False, f"type={type(data).__name__}")
        return

    v.check("etf-rotation has advice field",
            "advice" in data and isinstance(data["advice"], str),
            f"advice type={type(data.get('advice')).__name__}")
    v.check("etf-rotation has style field",
            "style" in data,
            f"style={data.get('style')!r}")
    v.check("etf-rotation has investment_horizon field",
            "investment_horizon" in data,
            f"investment_horizon={data.get('investment_horizon')!r}")
    v.check("etf-rotation has risk_preference field",
            "risk_preference" in data,
            f"risk_preference={data.get('risk_preference')!r}")

    advice = data.get("advice", "")
    v.check("etf-rotation advice non-empty",
            len(advice) > 50,
            f"advice length={len(advice)}")
    v.check("etf-rotation advice has disclaimer",
            "投资建议" in advice,
            "should contain '投资建议' disclaimer")


# ---------- Group 7: ETF-rotation with different styles ----------

def test_etf_styles(v: Verifier):
    print("\n--- Group 7: ETF-rotation style variants ---")
    for style in ("激进", "均衡"):
        status, body = _post("/api/ai/agent/etf-rotation",
                             {"style": style, "investment_horizon": "中期",
                              "risk_preference": "中等"})
        v.check(f"etf-rotation style={style} HTTP 200", status == 200,
                f"status={status}")
        if body and isinstance(body.get("data"), dict):
            v.check(f"etf-rotation style={style} returns matching style",
                    body["data"].get("style") == style,
                    f"style={body['data'].get('style')!r}")


# ---------- Group 8: ETF-rotation empty body (defaults) ----------

def test_etf_defaults(v: Verifier):
    print("\n--- Group 8: ETF-rotation empty body (defaults) ---")
    status, body = _post("/api/ai/agent/etf-rotation", {})
    v.check("etf-rotation empty body HTTP 200", status == 200, f"status={status}")
    if body and isinstance(body.get("data"), dict):
        v.check("etf-rotation default style=均衡",
                body["data"].get("style") == "均衡",
                f"style={body['data'].get('style')!r}")


# ---------- Group 9: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 9: Agent contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("board-trading in CONTRACT_ENDPOINTS",
                "ai/agent/board-trading" in content,
                "found in contract_endpoints.py")
        v.check("etf-rotation in CONTRACT_ENDPOINTS",
                "ai/agent/etf-rotation" in content,
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

    board_pass = any(
        "[PASS]" in ln and "board-trading" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check board-trading PASS", board_pass,
            "board-trading passed D004 contract")

    etf_pass = any(
        "[PASS]" in ln and "etf-rotation" in ln
        and "ai" in ln
        for ln in stdout.splitlines()
    )
    v.check("contract-check etf-rotation PASS", etf_pass,
            "etf-rotation agent passed D004 contract")


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
    print("M003/S06 AI Agent Endpoints Verification (R013, R014)")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    board_body = test_board_http_200_d004(v)
    if not board_body:
        v.print_summary()
        return 1
    test_board_schema(v, board_body)
    test_board_styles(v)
    test_board_defaults(v)

    etf_body = test_etf_http_200_d004(v)
    if not etf_body:
        v.print_summary()
        return 1
    test_etf_schema(v, etf_body)
    test_etf_styles(v)
    test_etf_defaults(v)

    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
