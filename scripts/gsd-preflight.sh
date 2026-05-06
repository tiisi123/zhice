#!/usr/bin/env bash
set -euo pipefail

echo "== GSD preflight =="

if [ -f ".gsd/auto.lock" ]; then
  echo "WARN: removing stale .gsd/auto.lock"
  rm -f .gsd/auto.lock
fi

if [ -d ".gsd" ]; then
  echo "== Empty plan files =="
  find .gsd -name "*-PLAN.md" -size 0 -print || true

  echo "== Existing plan files =="
  find .gsd -name "*-PLAN.md" -print | sort || true
else
  echo "INFO: .gsd directory not found. gsd-pi can still report repository state."
fi

if ! command -v gsd >/dev/null 2>&1; then
  echo "WARN: gsd CLI not found on PATH. Install gsd-pi before running auto mode:"
  echo "      npm install -g gsd-pi"
  echo "== Git status =="
  git status --short || true
  echo "== Preflight complete with warnings =="
  exit 0
fi

echo "== gsd version =="
gsd --version

echo "== gsd headless query =="
gsd headless --timeout 60000 query --output-format json

echo "== Git status =="
git status --short || true

echo "== Preflight complete =="
