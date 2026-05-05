#!/usr/bin/env bash
set -euo pipefail

echo "== GSD preflight =="

if [ ! -d ".gsd" ]; then
  echo "ERROR: .gsd directory not found"
  exit 1
fi

if [ -f ".gsd/auto.lock" ]; then
  echo "WARN: removing stale .gsd/auto.lock"
  rm -f .gsd/auto.lock
fi

echo "== Empty plan files =="
find .gsd -name "*-PLAN.md" -size 0 -print || true

echo "== Existing plan files =="
find .gsd -name "*-PLAN.md" -print | sort || true

echo "== gsd doctor =="
gsd doctor || {
  echo "WARN: gsd doctor reported issues"
  echo "Attempting gsd recover..."
  gsd recover
  gsd doctor
}

echo "== Git status =="
git status --short || true

echo "== Preflight complete =="
