#!/usr/bin/env bash
set -euo pipefail

echo "== GSD stuck recovery =="

rm -f .gsd/auto.lock

echo "Scanning for slice directories without plans..."

find .gsd/milestones -type d -path "*/slices/*" 2>/dev/null | while read -r dir; do
  slice="$(basename "$dir")"

  case "$slice" in
    S[0-9][0-9]|S[0-9][0-9][0-9])
      plan="$dir/${slice}-PLAN.md"

      if [ ! -f "$plan" ]; then
        echo "Creating missing plan: $plan"

        cat > "$plan" <<PLAN
# ${slice} Plan

## Recovery Note

This plan was created by \`scripts/gsd-recover-stuck.sh\` because the slice
directory existed but the durable plan artifact was missing.

## Slice Objective

Recover this slice by inspecting the milestone context, identifying the
intended work, and creating concrete verifiable tasks.

## Tasks

- [ ] **T01: Inspect current slice context** \`est:15m\`
  - Why: Auto-mode cannot safely continue without knowing the intended slice objective.
  - Files: \`${dir}/\`, nearby milestone files
  - Do: inspect existing milestone/slice artifacts, git status, recent changes
  - Verify: write the understood objective into this plan
  - Done when: the next implementation step is clear

- [ ] **T02: Make the smallest safe progress** \`est:30m\`
  - Why: Recovery should unblock GSD without expanding scope.
  - Files: TBD after T01
  - Do: implement or document the next concrete change, avoid broad refactors
  - Verify: run relevant tests/checks
  - Done when: progress is visible on disk and verified

- [ ] **T03: Rebuild and validate GSD state** \`est:10m\`
  - Why: GSD must observe durable progress from markdown.
  - Files: \`${plan}\`
  - Do: run \`gsd recover\`, run \`gsd doctor\`
  - Verify: no blocking GSD state errors remain
  - Done when: auto-mode can be resumed safely
PLAN
      fi
      ;;
  esac
done

echo "Running gsd recover..."
gsd headless --timeout 60000 recover

echo "Running gsd query..."
gsd headless --timeout 60000 query --output-format json

echo "== Recovery complete =="
