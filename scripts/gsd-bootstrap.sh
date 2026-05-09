#!/usr/bin/env bash
set -euo pipefail

milestone="${1:-M008}"
root=".gsd/milestones/${milestone}"

mkdir -p "${root}/slices"

context="${root}/${milestone}-CONTEXT.md"
roadmap="${root}/${milestone}-ROADMAP.md"

if [ ! -f "${context}" ]; then
  cat > "${context}" <<EOF
# ${milestone} Context

Bootstrap-created GSD context. Replace this with the milestone brief before running auto mode.
EOF
fi

if [ ! -f "${roadmap}" ]; then
  cat > "${roadmap}" <<EOF
# ${milestone} Roadmap

- [ ] S01: Define the first vertical slice.
EOF
fi

for slice in S01 S02 S03 S04 S05; do
  dir="${root}/slices/${slice}"
  plan="${dir}/${slice}-PLAN.md"
  mkdir -p "${dir}"
  if [ ! -f "${plan}" ]; then
    cat > "${plan}" <<EOF
# ${slice} Plan

## Objective

TBD.

## Tasks

- [ ] T01: Define and verify the first task.
EOF
  fi
done

echo "GSD bootstrap complete: ${root}"
