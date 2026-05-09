# S05 GSD Automation Bootstrap

## Objective

Make the repository ready for GSD auto once the CLI is installed.

## Tasks

- [x] T01: Add `.gsd` milestone and slice plan skeletons locally.
- [x] T02: Add versioned `docs/gsd` mirror for durable review.
- [x] T03: Add `make gsd-preflight`.
- [x] T04: Install or document GSD CLI setup.
- [x] T05: Run GSD preflight/recover checks and resolve reported blockers.

## Verification

- `gsd headless --timeout 60000 recover`
- `gsd headless --timeout 60000 query --output-format json`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/gsd-bootstrap.ps1 M008-CHECK2`

Note: `make gsd-preflight` was not executable in the current Windows shell because `make` is not installed; PowerShell and direct GSD commands were used instead.
