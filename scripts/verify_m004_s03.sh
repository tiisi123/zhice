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

echo "=== M004/S03 Verification: ETF 轮动信号 + 回测前端集成 ==="
echo ""

echo "--- 1. File existence ---"
check "EtfBacktestPanel.tsx exists" test -f src/components/EtfBacktestPanel.tsx
check "types.ts has EtfBacktestResult" grep -q "EtfBacktestResult" src/api/types.ts
check "types.ts has EtfRebalanceAllocation" grep -q "EtfRebalanceAllocation" src/api/types.ts

echo ""
echo "--- 2. D004 contract pattern ---"
check "EtfBacktestPanel imports fetchApi" grep -q "fetchApi" src/components/EtfBacktestPanel.tsx
check "EtfBacktestPanel imports extractMeta" grep -q "extractMeta" src/components/EtfBacktestPanel.tsx
check "EtfBacktestPanel imports DataStatusBadge" grep -q "DataStatusBadge" src/components/EtfBacktestPanel.tsx

echo ""
echo "--- 3. API endpoint usage ---"
check "EtfBacktestPanel calls /backtest/etf-rotation" grep -q "/backtest/etf-rotation" src/components/EtfBacktestPanel.tsx

echo ""
echo "--- 4. EtfRotationPage integration ---"
check "Imports EtfBacktestPanel" grep -q "EtfBacktestPanel" src/pages/EtfRotationPage.tsx
check "Has backtest tab key" grep -q "'backtest'" src/pages/EtfRotationPage.tsx
check "Lazy loads EtfBacktestPanel" grep -q "lazy.*EtfBacktestPanel" src/pages/EtfRotationPage.tsx
check "Existing sankey tab preserved" grep -q "sankey" src/pages/EtfRotationPage.tsx
check "Existing heatmap tab preserved" grep -q "heatmap" src/pages/EtfRotationPage.tsx

echo ""
echo "--- 5. UI states ---"
check "Has empty state" grep -q "暂无回测数据" src/components/EtfBacktestPanel.tsx
check "Has loading state (Spin)" grep -q "Spin" src/components/EtfBacktestPanel.tsx
check "Has ECharts chart" grep -q "echarts" src/components/EtfBacktestPanel.tsx
check "Has rebalance log" grep -q "rebalance_log" src/components/EtfBacktestPanel.tsx
check "Has collapsible sections" grep -q "Collapse" src/components/EtfBacktestPanel.tsx

echo ""
echo "--- 6. Metrics display ---"
check "Shows total_return" grep -q "total_return" src/components/EtfBacktestPanel.tsx
check "Shows annualized_return" grep -q "annualized_return" src/components/EtfBacktestPanel.tsx
check "Shows max_drawdown" grep -q "max_drawdown" src/components/EtfBacktestPanel.tsx
check "Shows sharpe_ratio" grep -q "sharpe_ratio" src/components/EtfBacktestPanel.tsx
check "Shows total_trades" grep -q "total_trades" src/components/EtfBacktestPanel.tsx

echo ""
echo "--- 7. Does NOT rebuild existing ETF page ---"
check "No duplicate /etf/rotation/dashboard call" bash -c '! grep -q "/etf/rotation/dashboard" src/components/EtfBacktestPanel.tsx'
check "No duplicate sankey in EtfBacktestPanel" bash -c '! grep -q "sankey" src/components/EtfBacktestPanel.tsx'

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
LINT_OUTPUT=$(npx eslint src/components/EtfBacktestPanel.tsx src/pages/EtfRotationPage.tsx src/api/types.ts 2>&1 || true)
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
