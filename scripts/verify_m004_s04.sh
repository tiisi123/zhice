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

echo "=== M004/S04 Verification: 打板回测前端页面 ==="
echo ""

echo "--- 1. File existence ---"
check "BoardBacktestPanel.tsx exists" test -f src/components/BoardBacktestPanel.tsx
check "types.ts has BoardBacktestResult" grep -q "BoardBacktestResult" src/api/types.ts
check "types.ts has BoardBacktestTradeEntry" grep -q "BoardBacktestTradeEntry" src/api/types.ts

echo ""
echo "--- 2. D004 contract pattern ---"
check "BoardBacktestPanel imports fetchApi" grep -q "fetchApi" src/components/BoardBacktestPanel.tsx
check "BoardBacktestPanel imports extractMeta" grep -q "extractMeta" src/components/BoardBacktestPanel.tsx
check "BoardBacktestPanel imports DataStatusBadge" grep -q "DataStatusBadge" src/components/BoardBacktestPanel.tsx

echo ""
echo "--- 3. API endpoint usage ---"
check "BoardBacktestPanel calls /backtest/board-strategy" grep -q "/backtest/board-strategy" src/components/BoardBacktestPanel.tsx

echo ""
echo "--- 4. Sub-strategy selector ---"
check "Has 首板 option" grep -q "首板" src/components/BoardBacktestPanel.tsx
check "Has 二板 option" grep -q "二板" src/components/BoardBacktestPanel.tsx
check "Has 龙头 option" grep -q "龙头" src/components/BoardBacktestPanel.tsx

echo ""
echo "--- 5. StrategyWorkshopPage integration ---"
check "Imports BoardBacktestPanel" grep -q "BoardBacktestPanel" src/pages/StrategyWorkshopPage.tsx
check "Has board-backtest tab key" grep -q "board-backtest" src/pages/StrategyWorkshopPage.tsx
check "Lazy loads BoardBacktestPanel" grep -q "lazy.*BoardBacktestPanel" src/pages/StrategyWorkshopPage.tsx

echo ""
echo "--- 6. UI states ---"
check "Has empty state" grep -q "暂无回测数据" src/components/BoardBacktestPanel.tsx
check "Has loading state (Spin)" grep -q "Spin" src/components/BoardBacktestPanel.tsx
check "Has ECharts chart" grep -q "echarts" src/components/BoardBacktestPanel.tsx
check "Has trade log table" grep -q "trade_log" src/components/BoardBacktestPanel.tsx

echo ""
echo "--- 7. Metrics display ---"
check "Shows total_return" grep -q "total_return" src/components/BoardBacktestPanel.tsx
check "Shows annualized_return" grep -q "annualized_return" src/components/BoardBacktestPanel.tsx
check "Shows max_drawdown" grep -q "max_drawdown" src/components/BoardBacktestPanel.tsx
check "Shows sharpe_ratio" grep -q "sharpe_ratio" src/components/BoardBacktestPanel.tsx
check "Shows win_rate" grep -q "win_rate" src/components/BoardBacktestPanel.tsx
check "Shows profit_loss_ratio" grep -q "profit_loss_ratio" src/components/BoardBacktestPanel.tsx
check "Shows max_consecutive_loss" grep -q "max_consecutive_loss" src/components/BoardBacktestPanel.tsx

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
LINT_OUTPUT=$(npx eslint src/components/BoardBacktestPanel.tsx src/pages/StrategyWorkshopPage.tsx src/api/types.ts 2>&1 || true)
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
