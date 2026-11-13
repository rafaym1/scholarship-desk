<#
  Scholarship Desk setup (Windows).

  .\setup.ps1                     folders, optional pypdf, git safety hook, desktop shortcut
  .\setup.ps1 -DailyWatch         also schedule the free daily page check (default 08:00)
  .\setup.ps1 -DailyWatch -WatchTime 19:30
  .\setup.ps1 -NoShortcut         skip the desktop shortcut

  If PowerShell blocks scripts, run:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>
param(
  [switch]$DailyWatch,
  [string]$WatchTime = "08:00",
  [switch]$NoShortcut
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# 1. Python 3.10+
$py = $null
foreach ($candidate in @("python", "py")) {
  if (Get-Command $candidate -ErrorAction SilentlyContinue) {
    $ok = & $candidate -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
    if ($ok -eq "True") { $py = $candidate; break }
  }
}
if (-not $py) {
  Write-Host "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again." -ForegroundColor Red
  exit 1
}
Write-Host "Python found: $py" -ForegroundColor Green

# 2. Required on Windows: time zone data, so deadlines are checked in the sponsor's time zone
& $py -c "import zoneinfo; zoneinfo.ZoneInfo('Europe/London')" 2>$null
if ($LASTEXITCODE -ne 0) {
  & $py -m pip install --user --quiet --disable-pip-version-check tzdata 2>$null
  & $py -c "import zoneinfo; zoneinfo.ZoneInfo('Europe/London')" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not install time zone data. Run '$py -m pip install tzdata', then run this setup again." -ForegroundColor Red
    exit 1
  }
  Write-Host "Time zone data installed (tzdata)."
}

# 3. Optional: pypdf for exact PDF page counts and merging
& $py -m pip install --user --quiet --disable-pip-version-check pypdf 2>$null
if ($LASTEXITCODE -eq 0) { Write-Host "pypdf installed (exact PDF page counts and merging)." }
else { Write-Host "pypdf not installed (optional): page counts will be approximate." -ForegroundColor Yellow }

# 4. Private folders
foreach ($dir in @("data", "data\tmp", "documents", "submitted", "playbooks")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $root $dir) | Out-Null
}
Write-Host "Folders ready. Put your CVs, transcripts and past essays in: $(Join-Path $root 'documents')"

# 5. Git safety hook (blocks committing CVs and profile data)
if ((Test-Path (Join-Path $root ".git")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
  git -C $root config core.hooksPath .githooks
  Write-Host "Git safety hook enabled."
}

# 6. Self-test
& $py -m scholar status | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Self-test failed: run '$py -m scholar status' to see why." -ForegroundColor Red; exit 1 }
Write-Host "Self-test passed." -ForegroundColor Green

# 7. Desktop shortcut for the dashboard
if (-not $NoShortcut) {
  $desktop = [Environment]::GetFolderPath("Desktop")
  $shell = New-Object -ComObject WScript.Shell
  $link = $shell.CreateShortcut((Join-Path $desktop "Scholarship Desk.lnk"))
  $link.TargetPath = Join-Path $root "start-dashboard.bat"
  $link.WorkingDirectory = $root
  $link.WindowStyle = 7
  $link.Description = "Open the Scholarship Desk dashboard"
  $link.Save()
  Write-Host "Desktop shortcut created: Scholarship Desk"
}

# 8. Optional daily watcher (free; no Claude usage). Runs late if the PC was off.
if ($DailyWatch) {
  $action = New-ScheduledTaskAction -Execute (Join-Path $root "scripts\daily-watch.bat") -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Daily -At $WatchTime
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  Register-ScheduledTask -TaskName "Scholarship Desk daily watch" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Checks watched scholarship pages once a day (no Claude usage)." -Force | Out-Null
  Write-Host "Daily watcher scheduled at $WatchTime (remove with: Unregister-ScheduledTask -TaskName 'Scholarship Desk daily watch')."
}

Write-Host ""
Write-Host "Next: open this folder in the Claude desktop app (Code tab) and run /profile." -ForegroundColor Cyan
