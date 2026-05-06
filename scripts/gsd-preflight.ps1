$ErrorActionPreference = "Stop"

Write-Host "== GSD preflight =="

if (!(Test-Path ".gsd")) {
  Write-Error "ERROR: .gsd directory not found"
  exit 1
}

if (Test-Path ".gsd/auto.lock") {
  Write-Host "WARN: removing stale .gsd/auto.lock"
  Remove-Item ".gsd/auto.lock" -Force
}

Write-Host "== Empty plan files =="
Get-ChildItem ".gsd" -Recurse -Filter "*-PLAN.md" |
  Where-Object { $_.Length -eq 0 } |
  ForEach-Object { $_.FullName }

Write-Host "== Existing plan files =="
Get-ChildItem ".gsd" -Recurse -Filter "*-PLAN.md" |
  Sort-Object FullName |
  ForEach-Object { $_.FullName }

$gsdCmd = Get-Command gsd -ErrorAction SilentlyContinue
if (!$gsdCmd) {
  Write-Host "WARN: gsd CLI not found on PATH. Install gsd before running auto mode."
  Write-Host "== Git status =="
  git status --short
  Write-Host "== Preflight complete with warnings =="
  exit 0
}

Write-Host "== gsd doctor =="
gsd doctor

Write-Host "== Git status =="
git status --short

Write-Host "== Preflight complete =="
