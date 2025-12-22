# =============================================================================
# 🚀 ABSTRACT WIKI ARCHITECT - BOOTSTRAPPER (v2.0)
# =============================================================================
# Logic has moved to 'manage.py'. This script just hands off control.
# =============================================================================

$ErrorActionPreference = "Stop"

# 1. VERSION CHECK
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Host "`n⚠️  WARNING: You are using Windows PowerShell 5.1" -ForegroundColor Yellow
    Start-Sleep -Seconds 1
}

Write-Host "`n🚀 Initializing Abstract Wiki Architect..." -ForegroundColor Cyan

# 2. AUTO-DETECT WSL PATH
# We still need this to tell WSL exactly where to run Python
$CurrentDir = (Get-Location).Path
$Drive = $CurrentDir.Substring(0, 1).ToLower()
$Path = $CurrentDir.Substring(2).Replace("\", "/")
$WSL_PATH = "/mnt/$Drive$Path"

Write-Host "   📂 Host: $CurrentDir" -ForegroundColor DarkGray
Write-Host "   🐧 WSL:  $WSL_PATH" -ForegroundColor DarkGray

# 3. HANDOFF TO PYTHON
# This runs the 'start' command in manage.py, which runs the full pipeline
# (Docker Check -> Process Kill -> Build -> Launch)
Write-Host "`n⚡ Handing control to Unified Commander (manage.py)..." -ForegroundColor Yellow

$Command = "cd '$WSL_PATH' && venv/bin/python manage.py start"
wsl bash -c $Command

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ Launch Failed. See errors above." -ForegroundColor Red
    exit $LASTEXITCODE
}