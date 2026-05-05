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

warn_check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $label"
    ((PASS++))
  else
    echo "  [WARN] $label"
    ((WARN++))
  fi
}

cd "$(dirname "$0")/../prototype/apps/web"

echo "=== M004/S01 Verification: 涨停复盘 + 游资席位前端看板 ==="
echo ""

echo "--- 1. File existence ---"
check "BoardReplayPanel.tsx exists" test -f src/components/BoardReplayPanel.tsx
check "TopTradersPanel.tsx exists" test -f src/components/TopTradersPanel.tsx
check "types.ts has BoardReplayData" grep -q "BoardReplayData" src/api/types.ts
check "types.ts has TopTraderStock" grep -q "TopTraderStock" src/api/types.ts
check "types.ts has EnrichedSeat" grep -q "EnrichedSeat" src/api/types.ts

echo ""
echo "--- 2. D004 contract pattern ---"
check "BoardReplayPanel imports fetchApi" grep -q "fetchApi" src/components/BoardReplayPanel.tsx
check "BoardReplayPanel imports extractMeta" grep -q "extractMeta" src/components/BoardReplayPanel.tsx
check "BoardReplayPanel imports DataStatusBadge" grep -q "DataStatusBadge" src/components/BoardReplayPanel.tsx
check "TopTradersPanel imports fetchApi" grep -q "fetchApi" src/components/TopTradersPanel.tsx
check "TopTradersPanel imports extractMeta" grep -q "extractMeta" src/components/TopTradersPanel.tsx
check "TopTradersPanel imports DataStatusBadge" grep -q "DataStatusBadge" src/components/TopTradersPanel.tsx

echo ""
echo "--- 3. API endpoint usage ---"
check "BoardReplayPanel calls /analysis/board-replay" grep -q "/analysis/board-replay" src/components/BoardReplayPanel.tsx
check "TopTradersPanel calls /analysis/top-traders" grep -q "/analysis/top-traders" src/components/TopTradersPanel.tsx

echo ""
echo "--- 4. ReplayPageV2 integration ---"
check "ReplayPageV2 imports BoardReplayPanel" grep -q "BoardReplayPanel" src/pages/ReplayPageV2.tsx
check "ReplayPageV2 imports TopTradersPanel" grep -q "TopTradersPanel" src/pages/ReplayPageV2.tsx
check "ReplayPageV2 has board-replay nav tab" grep -q "board-replay" src/pages/ReplayPageV2.tsx
check "ReplayPageV2 has top-traders nav tab" grep -q "top-traders" src/pages/ReplayPageV2.tsx

echo ""
echo "--- 5. UI states ---"
check "BoardReplayPanel has empty state" grep -q "暂无涨停复盘数据" src/components/BoardReplayPanel.tsx
check "BoardReplayPanel has loading state" grep -q "Spin" src/components/BoardReplayPanel.tsx
check "TopTradersPanel has empty state" grep -q "暂无龙虎榜数据" src/components/TopTradersPanel.tsx
check "TopTradersPanel has loading state" grep -q "Spin" src/components/TopTradersPanel.tsx

echo ""
echo "--- 6. TypeScript check ---"
if npx tsc --noEmit 2>&1; then
  echo "  [PASS] tsc --noEmit"
  ((PASS++))
else
  echo "  [FAIL] tsc --noEmit"
  ((FAIL++))
fi

echo ""
echo "--- 7. ESLint (4 critical rules) ---"
LINT_OUTPUT=$(npx eslint src/components/BoardReplayPanel.tsx src/components/TopTradersPanel.tsx src/pages/ReplayPageV2.tsx src/api/types.ts 2>&1 || true)
LINT_ERRORS=$(echo "$LINT_OUTPUT" | grep -oP '\(\K\d+(?= error)' || echo "0")
if [ "$LINT_ERRORS" -eq 0 ]; then
  echo "  [PASS] ESLint 0 errors"
  ((PASS++))
else
  echo "  [FAIL] ESLint $LINT_ERRORS errors"
  ((FAIL++))
fi

echo ""
echo "--- 8. Build check ---"
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
