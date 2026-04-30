param(
    [int]$ApiPort = 8010,
    [int]$WebPort = 5174
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$WebRoot = Join-Path $Root "apps/web"
$LogRoot = Join-Path $Root "data/cache"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$ApiLog = Join-Path $LogRoot "dev-api-$ApiPort.out.log"
$ApiErrLog = Join-Path $LogRoot "dev-api-$ApiPort.err.log"
$WebLog = Join-Path $LogRoot "dev-web-$WebPort.out.log"
$WebErrLog = Join-Path $LogRoot "dev-web-$WebPort.err.log"

function Test-HttpOk {
    param(
        [string]$Url,
        [string]$Expected
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ne 200) {
            return $false
        }
        if ($Expected -and -not ($response.Content -like "*$Expected*")) {
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [string]$Expected,
        [int]$TimeoutSec = 30
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url -Expected $Expected) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

Write-Host "[zhice] project root: $Root"
Write-Host "[zhice] API port: $ApiPort"
Write-Host "[zhice] Web port: $WebPort"
Write-Host "[zhice] API log: $ApiLog"
Write-Host "[zhice] API err: $ApiErrLog"
Write-Host "[zhice] Web log: $WebLog"
Write-Host "[zhice] Web err: $WebErrLog"

$apiCheck = Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue
if ($apiCheck) {
    if (Test-HttpOk -Url "http://127.0.0.1:$ApiPort/api/health" -Expected '"status"') {
        Write-Host "[zhice] API port $ApiPort already listening and healthy; reusing it."
    } else {
        throw "[zhice] API port $ApiPort is occupied but is not a healthy Zhice API. Pick another -ApiPort or stop the stale process."
    }
} else {
    Start-Process powershell -WindowStyle Hidden -RedirectStandardOutput $ApiLog -RedirectStandardError $ApiErrLog -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location '$Root'; python -m uvicorn apps.api.main:app --host 127.0.0.1 --port $ApiPort"
    )
    if (-not (Wait-HttpOk -Url "http://127.0.0.1:$ApiPort/api/health" -Expected '"status"' -TimeoutSec 30)) {
        throw "[zhice] API did not become healthy on $ApiPort. See $ApiLog and $ApiErrLog"
    }
}

$webCheck = Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue
if ($webCheck) {
    if (Test-HttpOk -Url "http://127.0.0.1:$WebPort/login" -Expected 'root') {
        Write-Host "[zhice] Web port $WebPort already listening and healthy; reusing it."
    } else {
        throw "[zhice] Web port $WebPort is occupied but is not a healthy Zhice web app. Pick another -WebPort or stop the stale process."
    }
} else {
    Start-Process powershell -WindowStyle Hidden -RedirectStandardOutput $WebLog -RedirectStandardError $WebErrLog -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location '$WebRoot'; `$env:VITE_API_PORT='$ApiPort'; npm run dev -- --host 127.0.0.1 --port $WebPort"
    )
    if (-not (Wait-HttpOk -Url "http://127.0.0.1:$WebPort/login" -Expected 'root' -TimeoutSec 30)) {
        throw "[zhice] Web did not become healthy on $WebPort. See $WebLog and $WebErrLog"
    }
}

$env:ZHICE_SMOKE_API_BASE = "http://127.0.0.1:$ApiPort"
$env:ZHICE_SMOKE_WEB_BASE = "http://127.0.0.1:$WebPort"
python (Join-Path $Root "scripts/smoke_test.py")

Write-Host "[zhice] verified web: http://127.0.0.1:$WebPort"
Write-Host "[zhice] verified api: http://127.0.0.1:$ApiPort"
