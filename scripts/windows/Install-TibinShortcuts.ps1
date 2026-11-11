param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

$ErrorActionPreference = "Stop"
$Name = "Tibin Runtime Control Center"
$Launcher = Join-Path $Root "scripts\windows\Start-TibinRuntime.ps1"
$Icon = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "$Name.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Tibin"
$StartMenuShortcut = Join-Path $StartMenuDir "$Name.lnk"
$TaskbarPinnedDir = Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
$TaskbarShortcut = Join-Path $TaskbarPinnedDir "$Name.lnk"
$StatusPath = Join-Path $Root "state\desktop_pin_status.json"

New-Item -ItemType Directory -Force -Path $StartMenuDir, $TaskbarPinnedDir, (Split-Path $StatusPath) | Out-Null

function New-TibinShortcut {
    param([string]$Path)
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
    $shortcut.WorkingDirectory = $Root
    $shortcut.IconLocation = "$Icon,0"
    $shortcut.Description = "Launch Tibin Runtime Control Center"
    $shortcut.Save()
}

New-TibinShortcut -Path $DesktopShortcut
New-TibinShortcut -Path $StartMenuShortcut
Copy-Item -LiteralPath $StartMenuShortcut -Destination $TaskbarShortcut -Force

$taskbarPinAttempt = "copied_to_taskbar_pinned_folder"
try {
    $shellApp = New-Object -ComObject Shell.Application
    $folder = $shellApp.Namespace((Split-Path $StartMenuShortcut))
    $item = $folder.ParseName((Split-Path $StartMenuShortcut -Leaf))
    $verb = $item.Verbs() | Where-Object { $_.Name.Replace('&', '') -match 'Pin to taskbar|Pin to Taskbar' } | Select-Object -First 1
    if ($verb) {
        $verb.DoIt()
        $taskbarPinAttempt = "shell_pin_verb_invoked"
    }
} catch {
    $taskbarPinAttempt = "shell_pin_verb_unavailable"
}

$status = [ordered]@{
    desktop_shortcut = $DesktopShortcut
    start_menu_shortcut = $StartMenuShortcut
    taskbar_shortcut = $TaskbarShortcut
    taskbar_pin_attempt = $taskbarPinAttempt
    created_at = (Get-Date).ToUniversalTime().ToString("o")
}

$status | ConvertTo-Json | Set-Content -LiteralPath $StatusPath -Encoding UTF8
Write-Output ($status | ConvertTo-Json)
