param(
  [string]$Milestone = "M008"
)

$root = Join-Path ".gsd/milestones" $Milestone
$slicesRoot = Join-Path $root "slices"
New-Item -ItemType Directory -Force -Path $slicesRoot | Out-Null

$context = Join-Path $root "$Milestone-CONTEXT.md"
$roadmap = Join-Path $root "$Milestone-ROADMAP.md"

if (-not (Test-Path $context)) {
  @"
# $Milestone Context

Bootstrap-created GSD context. Replace this with the milestone brief before running auto mode.
"@ | Set-Content -Path $context -Encoding UTF8
}

if (-not (Test-Path $roadmap)) {
  @"
# $Milestone Roadmap

- [ ] S01: Define the first vertical slice.
"@ | Set-Content -Path $roadmap -Encoding UTF8
}

foreach ($slice in @("S01", "S02", "S03", "S04", "S05")) {
  $dir = Join-Path $slicesRoot $slice
  $plan = Join-Path $dir "$slice-PLAN.md"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  if (-not (Test-Path $plan)) {
    @"
# $slice Plan

## Objective

TBD.

## Tasks

- [ ] T01: Define and verify the first task.
"@ | Set-Content -Path $plan -Encoding UTF8
  }
}

Write-Output "GSD bootstrap complete: $root"
