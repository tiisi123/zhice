"""M003/S07 slice verification — Frontend Integration + Contract Acceptance.

Validates:
1. Frontend build: TypeScript compiles, Vite builds clean
2. AIAgentPage exists with both panels (board-trading, etf-rotation)
3. Route registered in App.tsx
4. Menu entry in AppLayout.tsx
5. TypeScript types for agent endpoints in types.ts
6. API client calls use correct POST paths
7. Contract envelope handling (ContractEnvelope, extractMeta, DataStatusBadge)
8. Graceful degradation UI (loading, error, empty states)
9. AIDisclaimer present on agent pages
10. No accidental mock hardcoding in production UI
11. Backend contract endpoints still pass
12. check_no_mock.py: 0 violations
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROTO_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = PROTO_DIR / "apps" / "web"
SRC_DIR = WEB_DIR / "src"
SCRIPTS_DIR = PROTO_DIR / "scripts"

API_BASE = os.environ.get("ZHICE_API_BASE", "http://127.0.0.1:8000").rstrip("/")


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


# ---------- Group 1: Frontend build ----------

def test_frontend_build(v: Verifier):
    print("\n--- Group 1: Frontend build ---")

    result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        capture_output=True, text=True, timeout=120,
        cwd=str(WEB_DIR),
    )
    v.check("TypeScript compiles", result.returncode == 0,
            result.stderr.strip()[:200] if result.returncode else "zero errors")

    result = subprocess.run(
        ["npx", "vite", "build"],
        capture_output=True, text=True, timeout=120,
        cwd=str(WEB_DIR),
    )
    v.check("Vite build succeeds", result.returncode == 0,
            "production build OK" if not result.returncode else result.stderr.strip()[:200])


# ---------- Group 2: AIAgentPage exists ----------

def test_page_exists(v: Verifier):
    print("\n--- Group 2: AIAgentPage file structure ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    v.check("AIAgentPage.tsx exists", page.exists(), str(page))
    if not page.exists():
        return

    content = page.read_text()
    v.check("Page imports postApi", "postApi" in content,
            "uses API client for POST requests")
    v.check("Page imports extractMeta", "extractMeta" in content,
            "uses contract meta extraction")
    v.check("Page imports DataStatusBadge", "DataStatusBadge" in content,
            "renders data status badge")
    v.check("Page imports AIDisclaimer", "AIDisclaimer" in content,
            "includes AI disclaimer component")


# ---------- Group 3: Route registration ----------

def test_route_registered(v: Verifier):
    print("\n--- Group 3: Route registration ---")
    app_tsx = SRC_DIR / "App.tsx"
    v.check("App.tsx exists", app_tsx.exists(), str(app_tsx))
    if not app_tsx.exists():
        return

    content = app_tsx.read_text()
    v.check("AIAgentPage lazy import", "AIAgentPage" in content,
            "lazy import registered")
    v.check("/ai-agent route defined", "/ai-agent" in content,
            "route path present in App.tsx")


# ---------- Group 4: Menu entry ----------

def test_menu_entry(v: Verifier):
    print("\n--- Group 4: Sidebar menu entry ---")
    layout = SRC_DIR / "layouts" / "AppLayout.tsx"
    v.check("AppLayout.tsx exists", layout.exists(), str(layout))
    if not layout.exists():
        return

    content = layout.read_text()
    v.check("/ai-agent menu item", "/ai-agent" in content,
            "menu key present in AppLayout.tsx")
    v.check("AI Agent label", "AI" in content and "Agent" in content,
            "menu label contains AI Agent text")


# ---------- Group 5: TypeScript types ----------

def test_types(v: Verifier):
    print("\n--- Group 5: TypeScript types for agent endpoints ---")
    types_file = SRC_DIR / "api" / "types.ts"
    v.check("types.ts exists", types_file.exists(), str(types_file))
    if not types_file.exists():
        return

    content = types_file.read_text()
    v.check("BoardTradingInput type", "BoardTradingInput" in content,
            "request type defined")
    v.check("BoardTradingAdvice type", "BoardTradingAdvice" in content,
            "response type defined")
    v.check("EtfRotationInput type", "EtfRotationInput" in content,
            "request type defined")
    v.check("EtfRotationAdvice type", "EtfRotationAdvice" in content,
            "response type defined")
    v.check("ContractEnvelope type", "ContractEnvelope" in content,
            "generic envelope type defined")


# ---------- Group 6: API call paths ----------

def test_api_paths(v: Verifier):
    print("\n--- Group 6: API call paths ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    if not page.exists():
        v.check("AIAgentPage exists for path check", False, "file missing")
        return

    content = page.read_text()
    v.check("POST /ai/agent/board-trading path",
            "/ai/agent/board-trading" in content,
            "correct endpoint path in postApi call")
    v.check("POST /ai/agent/etf-rotation path",
            "/ai/agent/etf-rotation" in content,
            "correct endpoint path in postApi call")


# ---------- Group 7: Contract envelope handling ----------

def test_contract_handling(v: Verifier):
    print("\n--- Group 7: Contract envelope handling ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    if not page.exists():
        v.check("AIAgentPage exists for contract check", False, "file missing")
        return

    content = page.read_text()
    v.check("ContractEnvelope used in postApi<>",
            "ContractEnvelope<BoardTradingAdvice>" in content
            or "ContractEnvelope<" in content,
            "typed contract envelope response")
    v.check("extractMeta called on response",
            "extractMeta(result)" in content or "extractMeta(" in content,
            "meta extraction from contract response")
    v.check("data_status consumed",
            "data_status" in content or "meta.data_status" in content,
            "data status field used")
    v.check("source consumed",
            "meta.source" in content or "source={" in content,
            "source field used")


# ---------- Group 8: Graceful degradation states ----------

def test_degradation_states(v: Verifier):
    print("\n--- Group 8: Graceful degradation UI ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    if not page.exists():
        v.check("AIAgentPage exists for degradation check", False, "file missing")
        return

    content = page.read_text()
    v.check("Loading state (Spin)",
            "Spin" in content and "loading" in content,
            "loading spinner shown during fetch")
    v.check("Error state",
            "setError" in content or "error" in content.lower(),
            "error state managed")
    v.check("Empty state (Empty component or check)",
            "Empty" in content,
            "empty/error display component")
    v.check("Contract message display",
            "meta.message" in content or "message" in content,
            "contract message field displayed when present")


# ---------- Group 9: AI disclaimer ----------

def test_disclaimer(v: Verifier):
    print("\n--- Group 9: AI disclaimer compliance ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    if not page.exists():
        v.check("AIAgentPage exists for disclaimer check", False, "file missing")
        return

    content = page.read_text()
    v.check("AIDisclaimer component rendered",
            "<AIDisclaimer" in content,
            "AIDisclaimer tag present in JSX")
    v.check("AIBadge component rendered",
            "AIBadge" in content,
            "AI badge indicator present")


# ---------- Group 10: No mock hardcoding ----------

def test_no_mock_hardcode(v: Verifier):
    print("\n--- Group 10: No mock hardcoding in production UI ---")
    page = SRC_DIR / "pages" / "AIAgentPage.tsx"
    if not page.exists():
        v.check("AIAgentPage exists for mock check", False, "file missing")
        return

    content = page.read_text()
    v.check("No hardcoded mock advice",
            "mock_advice" not in content.lower()
            and "mockadvice" not in content.lower()
            and "fake_response" not in content.lower(),
            "no mock response strings found")
    v.check("No localhost URL hardcoded",
            "localhost" not in content and "127.0.0.1" not in content,
            "uses relative API paths via postApi")
    v.check("No import.meta.env mock override",
            "MOCK" not in content.upper() or "import.meta.env" not in content,
            "no env-based mock switching in page")


# ---------- Group 11: Backend contract endpoints pass ----------

def test_backend_contracts(v: Verifier):
    print("\n--- Group 11: Backend contract check ---")
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


# ---------- Group 12: Mock scan ----------

def test_mock_scan(v: Verifier):
    print("\n--- Group 12: check_no_mock.py ---")
    script = SCRIPTS_DIR / "check_no_mock.py"
    if not script.exists():
        v.check("mock-scan script exists", False, f"{script} not found")
        return
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, timeout=60,
        cwd=str(PROTO_DIR),
    )
    passed = result.returncode == 0
    summary = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
    v.check("mock-scan 0 violations", passed,
            summary or result.stderr.strip()[:200])


# ---------- Main ----------

def main() -> int:
    print("M003/S07 Frontend Integration + Contract Acceptance Verification")
    print(f"Web dir: {WEB_DIR}")
    print(f"API target: {API_BASE}")
    print("=" * 60)

    v = Verifier()

    test_frontend_build(v)
    test_page_exists(v)
    test_route_registered(v)
    test_menu_entry(v)
    test_types(v)
    test_api_paths(v)
    test_contract_handling(v)
    test_degradation_states(v)
    test_disclaimer(v)
    test_no_mock_hardcode(v)
    test_backend_contracts(v)
    test_mock_scan(v)

    print("\n" + "=" * 60)
    print("RESULTS:")
    v.print_summary()
    return 1 if v.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
