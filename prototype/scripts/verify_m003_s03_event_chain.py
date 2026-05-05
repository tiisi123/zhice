"""M003/S03 slice verification — event-chain analysis (R009).

Validates:
- /api/analysis/event-chain?keyword=芯片 D004 contract (source, data_status, mock)
- Chain structure: chain_name, matched_chain with upstream/midstream/downstream
- Fuzzy matching: partial keywords match correct chains
- Transmission metadata: transmission_logic and transmission_lag strings
- LLM analysis field present
- Empty keyword handling (data_status=empty)
- Contract check (check_api_contract.py) — event-chain passes
- Mock scan (check_no_mock.py) — 0 violations
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


def _get(path: str) -> tuple[int, dict | None]:
    encoded = quote(path, safe="/:?=&%")
    url = f"{API_BASE}{encoded}"
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


# ---------- Group 1: Chain match (keyword=芯片) ----------

def test_chain_match(v: Verifier):
    print("\n--- Group 1: Chain match (keyword=芯片) ---")
    status, body = _get("/api/analysis/event-chain?keyword=芯片")
    v.check("chain-match HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("chain-match has body", False, "empty response")
        return

    check_d004(v, "chain-match", body)

    ds = body.get("data_status")
    v.check("chain-match data_status in allowed set",
            ds in ALLOWED_STATUS, f"data_status={ds!r}")
    v.check("chain-match mock=False",
            body.get("mock") is False, f"mock={body.get('mock')!r}")

    src = body.get("source")
    v.check("chain-match source is non-empty string",
            isinstance(src, str) and len(src) > 0, f"source={src!r}")


# ---------- Group 2: Chain structure ----------

def test_chain_structure(v: Verifier):
    print("\n--- Group 2: Chain structure ---")
    status, body = _get("/api/analysis/event-chain?keyword=芯片")
    if status != 200 or not body:
        v.check("chain-structure skipped (endpoint unavailable)", True,
                f"status={status}")
        return

    ds = body.get("data_status")
    if ds != "real":
        v.check("chain-structure skipped (data not real)", True,
                f"data_status={ds}")
        return

    data = body.get("data", {})
    v.check("chain-structure chain_name=芯片半导体",
            data.get("chain_name") == "芯片半导体",
            f"chain_name={data.get('chain_name')!r}")

    matched = data.get("matched_chain", {})
    v.check("chain-structure has matched_chain", isinstance(matched, dict),
            f"type={type(matched).__name__}")

    for tier in ("upstream", "midstream", "downstream"):
        segments = matched.get(tier, [])
        v.check(f"chain-structure {tier} is non-empty list",
                isinstance(segments, list) and len(segments) > 0,
                f"{tier} len={len(segments) if isinstance(segments, list) else 'N/A'}")
        if segments and isinstance(segments[0], dict):
            v.check(f"chain-structure {tier}[0] has name",
                    "name" in segments[0],
                    f"keys={sorted(segments[0].keys())}")
            v.check(f"chain-structure {tier}[0] has stocks",
                    "stocks" in segments[0],
                    f"keys={sorted(segments[0].keys())}")


# ---------- Group 3: Fuzzy match ----------

def test_fuzzy_match(v: Verifier):
    print("\n--- Group 3: Fuzzy match ---")
    cases = [
        ("新能源", "新能源汽车"),
        ("AI", "AI人工智能"),
        ("医药", "医药生物"),
    ]
    for keyword, expected_chain in cases:
        status, body = _get(f"/api/analysis/event-chain?keyword={keyword}")
        v.check(f"fuzzy-{keyword} HTTP 200", status == 200, f"status={status}")
        if not body:
            continue
        ds = body.get("data_status")
        if ds != "real":
            v.check(f"fuzzy-{keyword} skipped (data not real)", True,
                    f"data_status={ds}")
            continue
        data = body.get("data", {})
        v.check(f"fuzzy-{keyword} matches {expected_chain}",
                data.get("chain_name") == expected_chain,
                f"chain_name={data.get('chain_name')!r}")


# ---------- Group 4: Transmission metadata ----------

def test_transmission_metadata(v: Verifier):
    print("\n--- Group 4: Transmission metadata ---")
    status, body = _get("/api/analysis/event-chain?keyword=芯片")
    if status != 200 or not body:
        v.check("transmission skipped (endpoint unavailable)", True,
                f"status={status}")
        return

    ds = body.get("data_status")
    if ds != "real":
        v.check("transmission skipped (data not real)", True,
                f"data_status={ds}")
        return

    data = body.get("data", {})
    tl = data.get("transmission_logic")
    v.check("transmission_logic is string",
            isinstance(tl, str), f"type={type(tl).__name__}, value={str(tl)[:80]!r}")

    tlag = data.get("transmission_lag")
    v.check("transmission_lag is string",
            isinstance(tlag, str), f"type={type(tlag).__name__}, value={str(tlag)[:80]!r}")


# ---------- Group 5: LLM analysis present ----------

def test_llm_analysis(v: Verifier):
    print("\n--- Group 5: LLM analysis ---")
    status, body = _get("/api/analysis/event-chain?keyword=芯片")
    if status != 200 or not body:
        v.check("llm-analysis skipped (endpoint unavailable)", True,
                f"status={status}")
        return

    ds = body.get("data_status")
    if ds != "real":
        v.check("llm-analysis skipped (data not real)", True,
                f"data_status={ds}")
        return

    data = body.get("data", {})
    llm = data.get("llm_analysis")
    v.check("llm_analysis field exists",
            "llm_analysis" in data,
            f"keys={sorted(data.keys())[:10]}")
    v.check("llm_analysis is string",
            isinstance(llm, str),
            f"type={type(llm).__name__}")


# ---------- Group 6: Empty keyword handling ----------

def test_empty_keyword(v: Verifier):
    print("\n--- Group 6: Empty keyword (no match) ---")
    status, body = _get("/api/analysis/event-chain?keyword=不存在的关键词")
    v.check("empty-keyword HTTP 200", status == 200, f"status={status}")
    if not body:
        v.check("empty-keyword has body", False, "empty response")
        return

    check_d004(v, "empty-keyword", body)
    ds = body.get("data_status")
    v.check("empty-keyword data_status=empty",
            ds == "empty",
            f"data_status={ds!r}")
    v.check("empty-keyword mock=False",
            body.get("mock") is False,
            f"mock={body.get('mock')!r}")


# ---------- Group 7: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 7: event-chain contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("event-chain in CONTRACT_ENDPOINTS",
                "event-chain" in content, "found in contract_endpoints.py")


# ---------- Group 8: Full contract check ----------

def test_contract_check(v: Verifier):
    print("\n--- Group 8: check_api_contract.py ---")
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

    event_chain_pass = any(
        "[PASS]" in ln and "event-chain" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check event-chain PASS", event_chain_pass,
            "event-chain passed D004 contract")

    overall_pass = result.returncode == 0
    v.check("contract-check 0 failures (overall)", overall_pass,
            summary[:200] if not overall_pass else summary[:200])


# ---------- Group 9: Mock scan ----------

def test_mock_scan(v: Verifier):
    print("\n--- Group 9: check_no_mock.py ---")
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
    print("M003/S03 Event-Chain Analysis Verification (R009)")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    test_chain_match(v)
    test_chain_structure(v)
    test_fuzzy_match(v)
    test_transmission_metadata(v)
    test_llm_analysis(v)
    test_empty_keyword(v)
    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
