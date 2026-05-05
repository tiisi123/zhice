"""M003/S04 slice verification — ETF rotation signals (R010).

Validates:
- GET /api/etf/rotation-signals returns HTTP 200
- D004 contract fields (source, data_status, mock)
- 13 ETF items in signals array
- Required per-signal fields (code, name, theme, signal, confidence, factors, reasoning, data_flag)
- Valid signal values (加仓/减仓/持有)
- Confidence range 0-100
- Factor scores structure (momentum, trend, volatility_safety)
- Determinism (repeated sample calls return identical results)
- Contract check (check_api_contract.py) — rotation-signals passes
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
VALID_SIGNALS = {"加仓", "减仓", "持有"}
REQUIRED_SIGNAL_FIELDS = {"code", "name", "theme", "signal", "confidence", "factors", "reasoning", "data_flag"}
REQUIRED_FACTORS = {"momentum", "trend", "volatility_safety"}


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


# ---------- Group 1: HTTP 200 ----------

def test_http_200(v: Verifier):
    print("\n--- Group 1: HTTP 200 (mode=sample) ---")
    status, body = _get("/api/etf/rotation-signals?mode=sample")
    v.check("rotation-signals HTTP 200", status == 200, f"status={status}")
    v.check("rotation-signals has body", body is not None, "non-null response")
    if body:
        data = body.get("data", {})
        v.check("rotation-signals has data key", isinstance(data, dict),
                f"type={type(data).__name__}")
    return body


# ---------- Group 2: D004 fields ----------

def test_d004_fields(v: Verifier, body: dict):
    print("\n--- Group 2: D004 contract fields ---")
    check_d004(v, "rotation-signals", body)
    src = body.get("source")
    v.check("rotation-signals source non-empty",
            isinstance(src, str) and len(src) > 0,
            f"source={src!r}")


# ---------- Group 3: 13 items ----------

def test_13_items(v: Verifier, body: dict):
    print("\n--- Group 3: 13 ETF items ---")
    data = body.get("data", {})
    signals = data.get("signals", [])
    v.check("signals is list", isinstance(signals, list),
            f"type={type(signals).__name__}")
    v.check("signals count == 13", len(signals) == 13,
            f"count={len(signals)}")
    codes = {s.get("code") for s in signals if isinstance(s, dict)}
    v.check("all codes unique", len(codes) == len(signals),
            f"unique={len(codes)} vs total={len(signals)}")
    return signals


# ---------- Group 4: Required fields ----------

def test_required_fields(v: Verifier, signals: list):
    print("\n--- Group 4: Required per-signal fields ---")
    for i, sig in enumerate(signals):
        if not isinstance(sig, dict):
            v.check(f"signal[{i}] is dict", False, f"type={type(sig).__name__}")
            continue
        missing = REQUIRED_SIGNAL_FIELDS - set(sig.keys())
        label = sig.get("code", f"idx-{i}")
        v.check(f"signal {label} fields complete", not missing,
                f"missing={sorted(missing)}" if missing else "all 8 fields present")
        if i == 0:
            break
    all_ok = all(
        isinstance(s, dict) and not (REQUIRED_SIGNAL_FIELDS - set(s.keys()))
        for s in signals
    )
    v.check("all 13 signals have required fields", all_ok,
            "checked code/name/theme/signal/confidence/factors/reasoning/data_flag")


# ---------- Group 5: Valid signals ----------

def test_valid_signals(v: Verifier, signals: list):
    print("\n--- Group 5: Valid signal values ---")
    invalid = []
    for s in signals:
        sig_val = s.get("signal") if isinstance(s, dict) else None
        if sig_val not in VALID_SIGNALS:
            invalid.append((s.get("code", "?"), sig_val))
    v.check("all signals in {加仓,减仓,持有}", not invalid,
            f"invalid={invalid}" if invalid else "all valid")
    from collections import Counter
    dist = Counter(s.get("signal") for s in signals if isinstance(s, dict))
    v.check("signal distribution present", len(dist) >= 1,
            f"distribution={dict(dist)}")


# ---------- Group 6: Confidence range ----------

def test_confidence_range(v: Verifier, signals: list):
    print("\n--- Group 6: Confidence range 0-100 ---")
    out_of_range = []
    non_int = []
    for s in signals:
        if not isinstance(s, dict):
            continue
        c = s.get("confidence")
        if not isinstance(c, int):
            non_int.append((s.get("code", "?"), type(c).__name__))
        elif c < 0 or c > 100:
            out_of_range.append((s.get("code", "?"), c))
    v.check("confidence all int", not non_int,
            f"non-int={non_int}" if non_int else "all int")
    v.check("confidence all 0-100", not out_of_range,
            f"out_of_range={out_of_range}" if out_of_range else "all in range")
    confs = [s["confidence"] for s in signals if isinstance(s, dict) and isinstance(s.get("confidence"), int)]
    if confs:
        v.check("confidence has variance", max(confs) != min(confs),
                f"min={min(confs)} max={max(confs)}")


# ---------- Group 7: Factor scores ----------

def test_factor_scores(v: Verifier, signals: list):
    print("\n--- Group 7: Factor scores structure ---")
    for i, s in enumerate(signals):
        if not isinstance(s, dict):
            continue
        factors = s.get("factors")
        label = s.get("code", f"idx-{i}")
        v.check(f"signal {label} factors is dict",
                isinstance(factors, dict),
                f"type={type(factors).__name__}")
        if isinstance(factors, dict):
            missing = REQUIRED_FACTORS - set(factors.keys())
            v.check(f"signal {label} has all 3 factors", not missing,
                    f"missing={sorted(missing)}" if missing else "momentum/trend/volatility_safety")
            for fk in REQUIRED_FACTORS:
                fv = factors.get(fk)
                v.check(f"signal {label} {fk} is numeric",
                        isinstance(fv, (int, float)),
                        f"{fk}={fv!r}")
        if i == 0:
            break
    all_ok = all(
        isinstance(s.get("factors"), dict) and not (REQUIRED_FACTORS - set(s["factors"].keys()))
        for s in signals if isinstance(s, dict)
    )
    v.check("all 13 signals have complete factors", all_ok,
            "checked momentum/trend/volatility_safety for all")


# ---------- Group 8: Determinism ----------

def test_determinism(v: Verifier):
    print("\n--- Group 8: Determinism (mode=sample) ---")
    _, body1 = _get("/api/etf/rotation-signals?mode=sample")
    _, body2 = _get("/api/etf/rotation-signals?mode=sample")
    if not body1 or not body2:
        v.check("determinism both calls returned data", False, "one or both calls failed")
        return
    sigs1 = body1.get("data", {}).get("signals", [])
    sigs2 = body2.get("data", {}).get("signals", [])
    v.check("determinism same count", len(sigs1) == len(sigs2),
            f"call1={len(sigs1)} call2={len(sigs2)}")
    if len(sigs1) == len(sigs2):
        codes1 = [s.get("code") for s in sigs1]
        codes2 = [s.get("code") for s in sigs2]
        v.check("determinism same order", codes1 == codes2,
                f"order matches" if codes1 == codes2 else f"order differs")
        signals_match = all(
            s1.get("signal") == s2.get("signal") and s1.get("confidence") == s2.get("confidence")
            for s1, s2 in zip(sigs1, sigs2)
        )
        v.check("determinism same signals+confidence", signals_match,
                "identical signals and confidence across calls")


# ---------- Group 9: Contract registration ----------

def test_contract_registration(v: Verifier):
    print("\n--- Group 9: rotation-signals contract registration ---")
    contract_file = SCRIPTS_DIR / "contract_endpoints.py"
    v.check("contract_endpoints.py exists", contract_file.exists(),
            str(contract_file))
    if contract_file.exists():
        content = contract_file.read_text()
        v.check("rotation-signals in CONTRACT_ENDPOINTS",
                "rotation-signals" in content, "found in contract_endpoints.py")


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

    rotation_signals_pass = any(
        "[PASS]" in ln and "rotation-signals" in ln for ln in stdout.splitlines()
    )
    v.check("contract-check rotation-signals PASS", rotation_signals_pass,
            "rotation-signals passed D004 contract")

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
    print("M003/S04 ETF Rotation Signals Verification (R010)")
    print(f"Target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    body = test_http_200(v)
    if not body:
        v.print_summary()
        return 1

    test_d004_fields(v, body)
    signals = test_13_items(v, body)
    test_required_fields(v, signals)
    test_valid_signals(v, signals)
    test_confidence_range(v, signals)
    test_factor_scores(v, signals)
    test_determinism(v)
    test_contract_registration(v)
    test_contract_check(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
