param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$Port = 5000,
    [switch]$StopFirst
)

$ErrorActionPreference = "Stop"
$Url = "http://127.0.0.1:$Port"
$HealthUrl = "$Url/health"
$StateDir = Join-Path $Root "state"
$LogsDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogsDir, $StateDir | Out-Null

function Test-TibinHealth {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
        if ($response.status -ne "ok") { return $false }
        if ($response.install_root -and ($response.install_root -ne $Root)) {
            Write-Warning "Health OK but install_root=$($response.install_root) differs from this folder: $Root"
            return $false
        }
        return $true
    } catch {
        return $false
    }
}

function Get-PythonCommand {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    throw "Python was not found on PATH."
}

if ($StopFirst) {
    $pythonExe = Get-PythonCommand
    & $pythonExe (Join-Path $Root "tibin.py") server --stop | Out-Null
    Start-Sleep -Seconds 1
}

$alreadyRunning = Test-TibinHealth
$processId = $null

if (-not $alreadyRunning) {
    $pythonExe = Get-PythonCommand
    $stdout = Join-Path $LogsDir "tibin-dashboard.out.log"
    $stderr = Join-Path $LogsDir "tibin-dashboard.err.log"
    $env:TIBIN_DEBUG = "0"

    # Canonical entry: run_server.py (uses process_manager + state/dashboard.pid)
    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("tibin.py", "server") `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    $processId = $process.Id

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-TibinHealth) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        throw "Dashboard did not become healthy at $HealthUrl. See $stderr"
    }
} else {
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2
        Write-Output "Using existing dashboard at $($health.install_root) branch=$($health.git_branch)"
    } catch {}
}

Start-Process $Url

$status = [ordered]@{
    status = "running"
    already_running = $alreadyRunning
    process_id = $processId
    url = $Url
    health_url = $HealthUrl
    root = $Root
    entry = "tibin.py server"
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
}

$statusJson = $status | ConvertTo-Json
Set-Content -LiteralPath (Join-Path $StateDir "desktop_launcher_status.json") -Value $statusJson -Encoding UTF8
Write-Output $statusJson
