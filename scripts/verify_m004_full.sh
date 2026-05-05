#!/usr/bin/env bash
set -uo pipefail

DIR="$(dirname "$0")"
TOTAL_PASS=0
TOTAL_FAIL=0
SLICES_OK=0
SLICES_FAIL=0

echo "============================================"
echo "  M004 Full Acceptance Verification"
echo "============================================"
echo ""

for s in 01 02 03 04 05; do
  SCRIPT="$DIR/verify_m004_s${s}.sh"
  if [ ! -f "$SCRIPT" ]; then
    echo "[SKIP] S${s} — script not found"
    continue
  fi
  echo ">>> Running S${s} verification..."
  OUTPUT=$(bash "$SCRIPT" 2>&1)
  RESULT_LINE=$(echo "$OUTPUT" | grep "^=== Results:")
  PASS=$(echo "$RESULT_LINE" | grep -oP '\d+(?= pass)' || echo "0")
  FAIL=$(echo "$RESULT_LINE" | grep -oP '\d+(?= fail)' || echo "0")
  TOTAL_PASS=$((TOTAL_PASS + PASS))
  TOTAL_FAIL=$((TOTAL_FAIL + FAIL))
  if [ "$FAIL" -eq 0 ]; then
    echo "  S${s}: ${PASS} pass, 0 fail  ✓"
    ((SLICES_OK++))
  else
    echo "  S${s}: ${PASS} pass, ${FAIL} fail  ✗"
    echo "$OUTPUT" | grep "\[FAIL\]" | sed 's/^/    /'
    ((SLICES_FAIL++))
  fi
  echo ""
done

echo "============================================"
echo "  M004 Summary"
echo "============================================"
echo "  Slices: $SLICES_OK pass, $SLICES_FAIL fail (of 5)"
echo "  Checks: $TOTAL_PASS pass, $TOTAL_FAIL fail"
echo "============================================"
exit $TOTAL_FAIL
