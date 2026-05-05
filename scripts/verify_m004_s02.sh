#!/usr/bin/env bash
set -uo pipefail

PASS=0
FAIL=0
WARN=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $label"
    ((PASS++))
  else
    echo "  [FAIL] $label"
    ((FAIL++))
  fi
}

cd "$(dirname "$0")/../prototype/apps/web"

echo "=== M004/S02 Verification: 事件影响链前端页面 ==="
echo ""

echo "--- 1. File existence ---"
check "EventChainPage.tsx exists" test -f src/pages/EventChainPage.tsx
check "types.ts has EventChainData" grep -q "EventChainData" src/api/types.ts

echo ""
echo "--- 2. D004 contract pattern ---"
check "EventChainPage imports fetchApi" grep -q "fetchApi" src/pages/EventChainPage.tsx
check "EventChainPage imports extractMeta" grep -q "extractMeta" src/pages/EventChainPage.tsx
check "EventChainPage imports DataStatusBadge" grep -q "DataStatusBadge" src/pages/EventChainPage.tsx

echo ""
echo "--- 3. API endpoint usage ---"
check "Calls /analysis/event-chain" grep -q "/analysis/event-chain" src/pages/EventChainPage.tsx
check "Uses encodeURIComponent" grep -q "encodeURIComponent" src/pages/EventChainPage.tsx

echo ""
echo "--- 4. Route registration ---"
check "App.tsx imports EventChainPage" grep -q "EventChainPage" src/App.tsx
check "App.tsx has /event-chain route" grep -q "event-chain" src/App.tsx
check "Lazy loads EventChainPage" grep -q "lazy.*EventChainPage" src/App.tsx

echo ""
echo "--- 5. Sidebar integration ---"
check "AppLayout has /event-chain key" grep -q "event-chain" src/layouts/AppLayout.tsx
check "AppLayout has 事件链 label" grep -q "事件链" src/layouts/AppLayout.tsx
check "AppLayout has ApartmentOutlined" grep -q "ApartmentOutlined" src/layouts/AppLayout.tsx

echo ""
echo "--- 6. UI features ---"
check "Has search input" grep -q "Search" src/pages/EventChainPage.tsx
check "Has upstream segment" grep -q "upstream" src/pages/EventChainPage.tsx
check "Has midstream segment" grep -q "midstream" src/pages/EventChainPage.tsx
check "Has downstream segment" grep -q "downstream" src/pages/EventChainPage.tsx
check "Has transmission_logic display" grep -q "transmission_logic" src/pages/EventChainPage.tsx
check "Has llm_analysis display" grep -q "llm_analysis" src/pages/EventChainPage.tsx
check "Has empty state" grep -q "输入关键词搜索事件链" src/pages/EventChainPage.tsx
check "Has loading state" grep -q "Spin" src/pages/EventChainPage.tsx

echo ""
echo "--- 7. Scope guard ---"
check "No backend changes (no new route files)" bash -c '! test -f ../../apps/api/routes/event_chain.py'
check "Page is simple tree/list (no force-directed graph)" bash -c '! grep -q "ForceGraph\|d3.force\|force-directed" src/pages/EventChainPage.tsx'

echo ""
echo "--- 8. TypeScript check ---"
if npx tsc --noEmit 2>&1; then
  echo "  [PASS] tsc --noEmit"
  ((PASS++))
else
  echo "  [FAIL] tsc --noEmit"
  ((FAIL++))
fi

echo ""
echo "--- 9. ESLint ---"
LINT_OUTPUT=$(npx eslint src/pages/EventChainPage.tsx src/App.tsx src/layouts/AppLayout.tsx src/api/types.ts 2>&1 || true)
LINT_ERRORS=$(echo "$LINT_OUTPUT" | grep -oP '\(\K\d+(?= error)' || echo "0")
if [ "$LINT_ERRORS" -eq 0 ]; then
  echo "  [PASS] ESLint 0 errors"
  ((PASS++))
else
  echo "  [FAIL] ESLint $LINT_ERRORS errors"
  ((FAIL++))
fi

echo ""
echo "--- 10. Build check ---"
if npm run build 2>&1 | grep -q "built in"; then
  echo "  [PASS] npm run build"
  ((PASS++))
else
  echo "  [FAIL] npm run build"
  ((FAIL++))
fi

echo ""
echo "=== Results: $PASS pass, $FAIL fail, $WARN warn ==="
exit $FAIL
