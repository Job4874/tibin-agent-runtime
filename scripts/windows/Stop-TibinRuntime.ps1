param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python not found on PATH." }

Write-Host "Stopping all Tibin processes (dashboard, watcher, port 5000)..."
& $python.Source (Join-Path $Root "runtime.py") --stop-all
Write-Host "Done."
