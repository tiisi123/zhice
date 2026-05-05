#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/web

PASS=0
FAIL=0
check() { if eval "$2" >/dev/null 2>&1; then echo "  ✅ $1"; ((PASS++)); else echo "  ❌ $1"; ((FAIL++)); fi; }

echo "=== M007/S01: Vitest 单测框架 + 核心页面测试 ==="

echo ""
echo "--- 1. Test infrastructure ---"
check "vitest installed" "npx vitest --version"
check "test script exists" "node -e \"require('./package.json').scripts.test || process.exit(1)\""
check "test:coverage script exists" "node -e \"require('./package.json').scripts['test:coverage'] || process.exit(1)\""
check "test-setup.ts exists" "test -f src/test-setup.ts"
check "vite.config.ts has test config" "grep -q 'test:' vite.config.ts"
check "@testing-library/react installed" "node -e \"require('@testing-library/react')\""
check "@testing-library/jest-dom installed" "node -e \"require('@testing-library/jest-dom')\""
check "happy-dom installed" "node -e \"require('happy-dom')\""
check "@vitest/coverage-v8 installed" "node -e \"require('@vitest/coverage-v8')\""

echo ""
echo "--- 2. Test files for 8 core pages ---"
check "LoginPage.test.tsx exists" "test -f src/__tests__/LoginPage.test.tsx"
check "ReplayPageV2.test.tsx exists" "test -f src/__tests__/ReplayPageV2.test.tsx"
check "AIAgentPage.test.tsx exists" "test -f src/__tests__/AIAgentPage.test.tsx"
check "EventChainPage.test.tsx exists" "test -f src/__tests__/EventChainPage.test.tsx"
check "EtfRotationPage.test.tsx exists" "test -f src/__tests__/EtfRotationPage.test.tsx"
check "StrategyWorkshopPage.test.tsx exists" "test -f src/__tests__/StrategyWorkshopPage.test.tsx"
check "IntradayPageV2.test.tsx exists" "test -f src/__tests__/IntradayPageV2.test.tsx"
check "GrowthWorkshopPage.test.tsx exists" "test -f src/__tests__/GrowthWorkshopPage.test.tsx"

echo ""
echo "--- 3. Tests pass ---"
check "npm run test passes" "npm run test"

echo ""
echo "--- 4. Coverage baseline ---"
check "coverage JSON exists" "npm run test:coverage && test -f coverage/coverage-summary.json"

echo ""
echo "--- 5. Build toolchain ---"
check "TypeScript compiles" "npm run typecheck"
check "ESLint passes" "npm run lint -- --max-warnings=999"
check "Vite build succeeds" "npm run build"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
