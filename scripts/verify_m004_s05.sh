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

echo "=== M004/S05 Verification: AI Agent 数据上下文增强 ==="
echo ""

echo "--- 1. File existence ---"
check "AIAgentPage.tsx exists" test -f src/pages/AIAgentPage.tsx

echo ""
echo "--- 2. D004 contract pattern ---"
check "AIAgentPage imports fetchApi" grep -q "fetchApi" src/pages/AIAgentPage.tsx
check "AIAgentPage imports extractMeta" grep -q "extractMeta" src/pages/AIAgentPage.tsx
check "AIAgentPage imports DataStatusBadge" grep -q "DataStatusBadge" src/pages/AIAgentPage.tsx

echo ""
echo "--- 3. Board data context ---"
check "BoardDataContext component exists" grep -q "BoardDataContext" src/pages/AIAgentPage.tsx
check "Fetches /analysis/board-replay" grep -q "/analysis/board-replay" src/pages/AIAgentPage.tsx
check "Shows first_board count" grep -q "first_board" src/pages/AIAgentPage.tsx
check "Shows consecutive count" grep -q "consecutive" src/pages/AIAgentPage.tsx
check "Shows broken count" grep -q "broken" src/pages/AIAgentPage.tsx
check "Has Collapse component" grep -q "Collapse" src/pages/AIAgentPage.tsx
check "Has lazy fetch pattern (fetched state)" grep -q "fetched" src/pages/AIAgentPage.tsx

echo ""
echo "--- 4. ETF data context ---"
check "EtfDataContext component exists" grep -q "EtfDataContext" src/pages/AIAgentPage.tsx
check "Fetches /etf/rotation/dashboard" grep -q "/etf/rotation/dashboard" src/pages/AIAgentPage.tsx
check "Shows data_mode tag" grep -q "data_mode" src/pages/AIAgentPage.tsx

echo ""
echo "--- 5. Integration ---"
check "BoardTradingPanel uses BoardDataContext" grep -A80 "function BoardTradingPanel" src/pages/AIAgentPage.tsx | grep -q "BoardDataContext"
check "EtfRotationPanel uses EtfDataContext" grep -A80 "function EtfRotationPanel" src/pages/AIAgentPage.tsx | grep -q "EtfDataContext"

echo ""
echo "--- 6. Scope guard ---"
check "No backend changes (no new route files)" bash -c '! test -f ../../apps/api/routes/ai_context.py'
check "No new page files (enhancement only)" bash -c '! test -f src/pages/AIAgentContextPage.tsx'

echo ""
echo "--- 7. TypeScript check ---"
if npx tsc --noEmit 2>&1; then
  echo "  [PASS] tsc --noEmit"
  ((PASS++))
else
  echo "  [FAIL] tsc --noEmit"
  ((FAIL++))
fi

echo ""
echo "--- 8. ESLint ---"
LINT_OUTPUT=$(npx eslint src/pages/AIAgentPage.tsx 2>&1 || true)
LINT_ERRORS=$(echo "$LINT_OUTPUT" | grep -oP '\(\K\d+(?= error)' || echo "0")
if [ "$LINT_ERRORS" -eq 0 ]; then
  echo "  [PASS] ESLint 0 errors"
  ((PASS++))
else
  echo "  [FAIL] ESLint $LINT_ERRORS errors"
  ((FAIL++))
fi

echo ""
echo "--- 9. Build check ---"
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
