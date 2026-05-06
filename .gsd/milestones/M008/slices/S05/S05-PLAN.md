# S05 Plan: GSD Automation Bootstrap

## Objective

Make the installed GSD CLI and repository scripts agree so plan -> slice -> task execution can continue from the PRD.

## Tasks

- [x] **T01: Install correct GSD CLI** `est:20m`
  - Files: local npm global environment.
  - Verify: `gsd --version` returns `2.80.0`.

- [x] **T02: Update preflight to supported headless commands** `est:25m`
  - Files: `scripts/gsd-preflight.ps1`, `scripts/gsd-preflight.sh`
  - Verify: PowerShell preflight completes.

- [x] **T03: Update recover script to supported headless commands** `est:15m`
  - Files: `scripts/gsd-recover-stuck.sh`
  - Verify: script calls `gsd headless recover/query`, not removed top-level `doctor/recover`.

- [ ] **T04: Import M008 projection into GSD DB** `est:15m`
  - Files: `.gsd/milestones/M008/**`
  - Verify: `gsd headless recover` imports nonzero M/S/T and query sees active milestone.
