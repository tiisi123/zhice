"""S02 slice verification — exercises four DFCF value endpoints via direct function calls.

Validates:
- get_financial_reports, get_research_reports, get_expectations (valuation.py)
- get_expectation_history (macro/data.py)
- All return list[dict], never mock-shaped data
- Invalid stock code returns empty list (no crash)
- Mock dicts fully removed from source modules
"""

from __future__ import annotations

import inspect
import sys
import time

import os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))


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


def test_financial_reports(v: Verifier):
    """get_financial_reports('600519') — expect list of DFCF announcements."""
    print("\n--- get_financial_reports('600519') ---")
    from packages.features.valuation import get_financial_reports
    start = time.time()
    result = get_financial_reports("600519")
    dur = time.time() - start
    v.check("reports returns list", isinstance(result, list), f"type={type(result).__name__}")
    v.check("reports no sample_ fields", not _has_sample_field(result), _sample_detail(result))
    if result:
        v.check("reports non-empty (DFCF reachable)", True, f"count={len(result)}")
        r0 = result[0]
        v.check("reports[0] has title", "title" in r0, f"keys={sorted(r0.keys())}")
        v.check("reports[0] has notice_date", "notice_date" in r0, f"keys={sorted(r0.keys())}")
    else:
        print(f"  [INFO] reports returned empty — DFCF may be unreachable ({dur:.1f}s)")


def test_research_reports(v: Verifier):
    """get_research_reports('600519') — expect list of DFCF research reports."""
    print("\n--- get_research_reports('600519') ---")
    from packages.features.valuation import get_research_reports
    start = time.time()
    result = get_research_reports("600519")
    dur = time.time() - start
    v.check("research returns list", isinstance(result, list), f"type={type(result).__name__}")
    v.check("research no sample_ fields", not _has_sample_field(result), _sample_detail(result))
    if result:
        v.check("research non-empty (DFCF reachable)", True, f"count={len(result)}")
        r0 = result[0]
        v.check("research[0] has org", "org" in r0, f"keys={sorted(r0.keys())}")
        v.check("research[0] has rating", "rating" in r0, f"keys={sorted(r0.keys())}")
    else:
        print(f"  [INFO] research returned empty — DFCF may be unreachable ({dur:.1f}s)")


def test_expectations(v: Verifier):
    """get_expectations('600519') — expect list of analyst expectations."""
    print("\n--- get_expectations('600519') ---")
    from packages.features.valuation import get_expectations
    start = time.time()
    result = get_expectations("600519")
    dur = time.time() - start
    v.check("expectations returns list", isinstance(result, list), f"type={type(result).__name__}")
    v.check("expectations no sample_ fields", not _has_sample_field(result), _sample_detail(result))
    if result:
        v.check("expectations non-empty (DFCF reachable)", True, f"count={len(result)}")
        r0 = result[0]
        v.check("expectations[0] has broker", "broker" in r0, f"keys={sorted(r0.keys())}")
        v.check("expectations[0] has rating", "rating" in r0, f"keys={sorted(r0.keys())}")
    else:
        print(f"  [INFO] expectations returned empty — DFCF may be unreachable ({dur:.1f}s)")


def test_expectation_history(v: Verifier):
    """get_expectation_history('600519') — expect list of month-bucketed entries."""
    print("\n--- get_expectation_history('600519') ---")
    from packages.features.macro.data import get_expectation_history
    start = time.time()
    result = get_expectation_history("600519")
    dur = time.time() - start
    v.check("history returns list", isinstance(result, list), f"type={type(result).__name__}")
    v.check("history no sample_ fields", not _has_sample_field(result), _sample_detail(result))
    if result:
        v.check("history non-empty (DFCF reachable)", True, f"count={len(result)}")
        r0 = result[0]
        v.check("history[0] has date", "date" in r0, f"keys={sorted(r0.keys())}")
    else:
        print(f"  [INFO] history returned empty — DFCF may be unreachable ({dur:.1f}s)")


def test_invalid_code(v: Verifier):
    """All four functions with '999999' — should return empty list, not crash."""
    print("\n--- invalid code '999999' ---")
    from packages.features.valuation import get_financial_reports, get_research_reports, get_expectations
    from packages.features.macro.data import get_expectation_history

    for name, fn in [
        ("reports-invalid", get_financial_reports),
        ("research-invalid", get_research_reports),
        ("expectations-invalid", get_expectations),
        ("history-invalid", get_expectation_history),
    ]:
        try:
            result = fn("999999")
            v.check(f"{name} returns list", isinstance(result, list), f"type={type(result).__name__}")
            v.check(f"{name} returns empty", len(result) == 0, f"count={len(result)}")
        except Exception as e:
            v.check(f"{name} no crash", False, f"exception: {e}")


def test_no_mock_dicts(v: Verifier):
    """Verify mock dicts removed from source modules."""
    print("\n--- mock dict removal ---")
    import packages.features.valuation as val_mod
    import packages.features.macro.data as macro_mod

    val_src = inspect.getsource(val_mod)
    macro_src = inspect.getsource(macro_mod)

    v.check("FINANCIAL_REPORTS removed", "FINANCIAL_REPORTS" not in val_src,
            "dict still exists" if "FINANCIAL_REPORTS" in val_src else "removed")
    v.check("RESEARCH_REPORTS removed", "RESEARCH_REPORTS" not in val_src,
            "dict still exists" if "RESEARCH_REPORTS" in val_src else "removed")
    v.check("ANALYST_EXPECTATIONS removed", "ANALYST_EXPECTATIONS" not in val_src,
            "dict still exists" if "ANALYST_EXPECTATIONS" in val_src else "removed")
    v.check("EXPECTATION_HISTORY removed", "EXPECTATION_HISTORY" not in macro_src,
            "dict still exists" if "EXPECTATION_HISTORY" in macro_src else "removed")


def _has_sample_field(items: list[dict]) -> bool:
    for item in items:
        for k, val in item.items():
            if isinstance(val, str) and "sample_" in val:
                return True
    return False


def _sample_detail(items: list[dict]) -> str:
    for item in items:
        for k, val in item.items():
            if isinstance(val, str) and "sample_" in val:
                return f"found sample_ in {k}={val!r}"
    return "no sample_ fields"


def main() -> int:
    print("S02 Value Endpoints Verification (reports/research/expectations/history)")
    print("=" * 60)

    v = Verifier()
    test_financial_reports(v)
    test_research_reports(v)
    test_expectations(v)
    test_expectation_history(v)
    test_invalid_code(v)
    test_no_mock_dicts(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
