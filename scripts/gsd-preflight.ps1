$ErrorActionPreference = "Stop"

Write-Host "== GSD preflight =="

if (Test-Path ".gsd/auto.lock") {
  Write-Host "WARN: removing stale .gsd/auto.lock"
  Remove-Item ".gsd/auto.lock" -Force
}

if (Test-Path ".gsd") {
  Write-Host "== Empty plan files =="
  Get-ChildItem ".gsd" -Recurse -Filter "*-PLAN.md" |
    Where-Object { $_.Length -eq 0 } |
    ForEach-Object { $_.FullName }

  Write-Host "== Existing plan files =="
  Get-ChildItem ".gsd" -Recurse -Filter "*-PLAN.md" |
    Sort-Object FullName |
    ForEach-Object { $_.FullName }
} else {
  Write-Host "INFO: .gsd directory not found. gsd-pi can still report repository state."
}

$gsdCmd = Get-Command gsd -ErrorAction SilentlyContinue
if (!$gsdCmd) {
  Write-Host "WARN: gsd CLI not found on PATH. Install gsd-pi before running auto mode:"
  Write-Host "      npm install -g gsd-pi"
  Write-Host "== Git status =="
  git status --short
  Write-Host "== Preflight complete with warnings =="
  exit 0
}

Write-Host "== gsd version =="
gsd --version

Write-Host "== gsd headless query =="
gsd headless --timeout 60000 query --output-format json

Write-Host "== Git status =="
git status --short

Write-Host "== Preflight complete =="
