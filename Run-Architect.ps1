<#
.SYNOPSIS
    Semantik Architect Launcher (Windows orchestrator).
    - Verbose output is ON by default (use -NoVerbose to silence)
    - Optionally kills project-related node.exe (or all node.exe with -KillAllNode)
    - Starts API in WSL (uvicorn) and Worker in WSL (arq)
    - Starts frontend in Windows (npm run dev)
    - Writes WSL helper scripts into .\logs and keeps WSL windows open for debugging
    - Performs a reliable backend readiness probe (HTTP) with retries

.NOTES
    Recommended:
      pwsh -NoExit -NoProfile -ExecutionPolicy Bypass -File .\Run-Architect.ps1
    PowerShell requires explicit path:
      .\Run-Architect.ps1   (not Run-Architect.ps1)
#>

[CmdletBinding()]
param(
    [switch]$KillAllNode,
    [switch]$SkipApi,
    [switch]$SkipWorker,
    [switch]$SkipFrontend,
    [switch]$SkipBrowser,
    [switch]$NoVerbose,
    [switch]$CleanupOnly,

    # Default is OFF to avoid watchfiles crashes in WSL.
    # Use -EnableReload / -EnableWatch only if you explicitly want file-watching reloads.
    [switch]$EnableReload,
    [switch]$EnableWatch,

    # Prevents killing an already-running backend on reruns (recommended when you are only relaunching frontend/browser).
    [switch]$NoPortClear,

    [string]$WinRepoOverride = "",
    [int]$BackendPort = 8000,
    [int]$BrowserDelaySeconds = 5,
    [string]$LaunchUrl = "http://localhost:3000/semantik_architect/tools",

    # Backend HTTP probe retry window (seconds)
    [int]$BackendProbeTimeoutSeconds = 10
)

Set-StrictMode -Version Latest

# Verbose default
$VerbosePreference = if ($NoVerbose) { 'SilentlyContinue' } else { 'Continue' }
$ErrorActionPreference = 'Stop'

function Get-PreferredPsHostExe {
    if (Get-Command pwsh -ErrorAction SilentlyContinue) { return "pwsh" }
    return "powershell"
}

function Convert-ToWslPath([string]$WinPath) {
    # Works even if target doesn't exist
    $full = [System.IO.Path]::GetFullPath($WinPath)
    if ($full -match '^([A-Za-z]):\\(.*)$') {
        $drive = $matches[1].ToLower()
        $rest  = $matches[2] -replace '\\','/'
        return "/mnt/$drive/$rest"
    }
    throw "Unsupported Windows path format: $full"
}

function Write-TextFileLF([string]$Path, [string]$Content) {
    $text = ($Content -replace "`r`n", "`n") -replace "`r", "`n"
    if (-not $text.EndsWith("`n")) { $text += "`n" }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $text, $utf8NoBom)
}

function Start-WslPwshWindow {
    param(
        [Parameter(Mandatory=$true)][string]$Title,
        [Parameter(Mandatory=$true)][string]$WslRepo,
        [Parameter(Mandatory=$true)][string]$BashCmd,
        [Parameter(Mandatory=$true)][string]$LogHint
    )

    $psHost = Get-PreferredPsHostExe
    $helperPath = Join-Path $env:TEMP ("ska_" + [Guid]::NewGuid().ToString("N") + ".ps1")

    # Use single-quoted here-string so PS does not expand $ or $(...)
    $helperContent = @"
`$host.UI.RawUI.WindowTitle = '$Title'
`$VerbosePreference = 'Continue'
`$ErrorActionPreference = 'Continue'

Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '  $Title' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host 'WSL repo: $WslRepo' -ForegroundColor Gray
Write-Host 'Logs:     $LogHint' -ForegroundColor Gray
Write-Host ''

`$BashCmd = @'
$BashCmd
'@.Trim()

& wsl.exe --cd '$WslRepo' --exec bash -lc `$BashCmd

Write-Host ''
if (`$LASTEXITCODE -eq 0) {
  Write-Host ('WSL session ended (code 0).') -ForegroundColor DarkGray
} else {
  Write-Host ('WSL exited with code: ' + `$LASTEXITCODE) -ForegroundColor Yellow
}
Read-Host 'Press Enter to close this window' | Out-Null
"@

    Set-Content -Path $helperPath -Value $helperContent -Encoding UTF8
    Start-Process $psHost -ArgumentList @("-NoExit","-NoProfile","-ExecutionPolicy","Bypass","-File",$helperPath)
}

function Invoke-WslBackendProbe {
    param(
        [Parameter(Mandatory=$true)][int]$Port,
        [Parameter(Mandatory=$true)][int]$TimeoutSeconds
    )

    for ($i = 1; $i -le $TimeoutSeconds; $i++) {
        $out = & wsl.exe --exec bash -lc "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$Port/api/v1/health/ready || true"
        if ($out -eq "200") {
            Write-Host "READY_200" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }

    Write-Host "NOT_READY" -ForegroundColor Yellow
}

# -----------------------------
# 0) Resolve repo paths
# -----------------------------
$DefaultWinRepo = "C:\MyCode\SemantiK_Architect\Semantik_architect"

$WinRepo =
    if ($WinRepoOverride) { $WinRepoOverride }
    elseif (Test-Path (Join-Path $PSScriptRoot "manage.py")) { $PSScriptRoot }
    else { $DefaultWinRepo }

if (-not (Test-Path $WinRepo)) {
    Write-Error "Repo path not found: $WinRepo"
    exit 1
}

$WinRepo = [System.IO.Path]::GetFullPath($WinRepo)
$ManagePy = Join-Path $WinRepo "manage.py"
$FrontendDir = Join-Path $WinRepo "architect_frontend"
$LogsDirWin = Join-Path $WinRepo "logs"

if (-not (Test-Path $ManagePy)) {
    Write-Error "manage.py not found at: $ManagePy"
    exit 1
}

if (-not (Test-Path $LogsDirWin)) {
    New-Item -ItemType Directory -Path $LogsDirWin | Out-Null
}

$WslRepo = Convert-ToWslPath $WinRepo

# -----------------------------
# 1) Header
# -----------------------------
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   SEMANTIK ARCHITECT - LAUNCHER" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Windows repo: $WinRepo" -ForegroundColor Gray
Write-Host "WSL repo:     $WslRepo" -ForegroundColor Gray
Write-Host "Logs dir:     $LogsDirWin" -ForegroundColor Gray

Write-Verbose "Parameters:"
Write-Verbose "  KillAllNode=$KillAllNode"
Write-Verbose "  SkipApi=$SkipApi SkipWorker=$SkipWorker SkipFrontend=$SkipFrontend SkipBrowser=$SkipBrowser"
Write-Verbose "  CleanupOnly=$CleanupOnly"
Write-Verbose "  EnableReload=$EnableReload EnableWatch=$EnableWatch"
Write-Verbose "  NoPortClear=$NoPortClear"
Write-Verbose "  BackendPort=$BackendPort"
Write-Verbose "  BrowserDelaySeconds=$BrowserDelaySeconds"
Write-Verbose "  LaunchUrl=$LaunchUrl"
Write-Verbose "  BackendProbeTimeoutSeconds=$BackendProbeTimeoutSeconds"

# -----------------------------
# 2) Sanity checks
# -----------------------------
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Write-Error "wsl.exe not found. Install/enable WSL first."
    exit 1
}

# -----------------------------
# 3) Cleanup (Windows + WSL port)
# -----------------------------
Write-Host "`n[1/3] Cleaning up processes..." -ForegroundColor Yellow

if ($KillAllNode) {
    if (Get-Process node -ErrorAction SilentlyContinue) {
        Stop-Process -Name node -Force -ErrorAction SilentlyContinue
        Write-Host "  - Killed ALL node.exe processes" -ForegroundColor Gray
    } else {
        Write-Host "  - No node.exe processes found" -ForegroundColor Gray
    }
} else {
    $nodeCandidates = Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
        Where-Object {
            $_.CommandLine -and (
                $_.CommandLine -like "*$FrontendDir*" -or
                $_.CommandLine -like "*$WinRepo*"
            )
        }

    if ($nodeCandidates) {
        foreach ($p in $nodeCandidates) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
        Write-Host "  - Killed project-related node.exe processes" -ForegroundColor Gray
    } else {
        Write-Host "  - No project-related node.exe processes found" -ForegroundColor Gray
    }
}

# Clear backend port in WSL only when we intend to (avoid killing a healthy backend on rerun)
if (-not $NoPortClear -and -not $SkipApi) {
    try {
        $killPortCmd = "command -v fuser >/dev/null 2>&1 && fuser -k $BackendPort/tcp >/dev/null 2>&1 || true"
        wsl.exe --exec bash -lc $killPortCmd | Out-Null
        Write-Host "  - Cleared port $BackendPort (WSL)" -ForegroundColor Gray
    } catch {
        Write-Warning "WSL port cleanup warnings: $($_.Exception.Message)"
    }
} else {
    Write-Host "  - Port clear skipped (NoPortClear or SkipApi enabled)" -ForegroundColor Gray
}

if ($CleanupOnly) {
    Write-Host "`nCleanupOnly requested; exiting after cleanup." -ForegroundColor Yellow
    exit 0
}

# -----------------------------
# 4) Write WSL helper scripts into .\logs
# -----------------------------
$ApiScriptWin    = Join-Path $LogsDirWin "start_api.sh"
$WorkerScriptWin = Join-Path $LogsDirWin "start_worker.sh"

$uvicornReload = if ($EnableReload) { "--reload" } else { "" }
$arqWatch      = if ($EnableWatch)  { "--watch app" } else { "" }

# IMPORTANT: single-quoted here-strings so PowerShell does not expand ${TS}, $ROOT, $(...)
$commonHeader = @'
#!/usr/bin/env bash
set +e
set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

TS="$(date +%Y%m%d_%H%M%S)"
mkdir -p logs

# Reduce watchfiles/inotify pressure on some WSL setups
export WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-1}"
export PYTHONUNBUFFERED=1

pick_venv() {
  if [ -f venv/bin/activate ]; then echo "venv"; return; fi
  if [ -f .venv/bin/activate ]; then echo ".venv"; return; fi
  echo ""
}
'@.Trim()

$apiScript = @'
__COMMON__

LOGFILE="logs/api_${TS}.log"
echo "Logging to: ${ROOT}/${LOGFILE}"
exec > >(tee -a "${LOGFILE}") 2>&1

echo "PWD=$(pwd)"
echo "WSL=$(uname -a)"

VENV="$(pick_venv)"
if [ -n "$VENV" ]; then
  # shellcheck disable=SC1090
  source "${VENV}/bin/activate"
  echo "VENV_OK=${VIRTUAL_ENV}"
else
  echo "VENV_MISSING: expected venv/ or .venv/ in $(pwd)"
fi

echo "PY=$(command -v python3 2>/dev/null || true)"
python3 --version 2>/dev/null || true

echo ""
echo "PGF check:"
ls -l gf/semantik_architect.pgf 2>/dev/null || echo "MISSING_PGF"

PORT="${1:-8000}"
RELOAD_ARGS="__UVICORN_RELOAD__"

echo ""
echo "Starting API:"
echo "  python3 -m uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port ${PORT} ${RELOAD_ARGS}"
python3 -m uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port "${PORT}" ${RELOAD_ARGS}
STATUS=$?
echo "uvicorn exit code: ${STATUS}"

echo ""
echo "Dropping into an interactive shell."
exec bash -li
'@.Trim().Replace('__COMMON__', $commonHeader).Replace('__UVICORN_RELOAD__', $uvicornReload)

$workerScript = @'
__COMMON__

LOGFILE="logs/worker_${TS}.log"
echo "Logging to: ${ROOT}/${LOGFILE}"
exec > >(tee -a "${LOGFILE}") 2>&1

echo "PWD=$(pwd)"
echo "WSL=$(uname -a)"

VENV="$(pick_venv)"
if [ -n "$VENV" ]; then
  # shellcheck disable=SC1090
  source "${VENV}/bin/activate"
  echo "VENV_OK=${VIRTUAL_ENV}"
else
  echo "VENV_MISSING: expected venv/ or .venv/ in $(pwd)"
fi

echo "PY=$(command -v python3 2>/dev/null || true)"
python3 --version 2>/dev/null || true

WATCH_ARGS="__ARQ_WATCH__"

echo ""
echo "Starting worker:"
echo "  python3 -m arq app.workers.worker.WorkerSettings ${WATCH_ARGS}"
python3 -m arq app.workers.worker.WorkerSettings ${WATCH_ARGS}
STATUS=$?
echo "worker exit code: ${STATUS}"

echo ""
echo "Dropping into an interactive shell."
exec bash -li
'@.Trim().Replace('__COMMON__', $commonHeader).Replace('__ARQ_WATCH__', $arqWatch)

Write-TextFileLF -Path $ApiScriptWin    -Content $apiScript
Write-TextFileLF -Path $WorkerScriptWin -Content $workerScript

if (-not (Test-Path $ApiScriptWin))    { throw "Failed to write: $ApiScriptWin" }
if (-not (Test-Path $WorkerScriptWin)) { throw "Failed to write: $WorkerScriptWin" }

Write-Verbose "Wrote WSL scripts:"
Write-Verbose "  $ApiScriptWin"
Write-Verbose "  $WorkerScriptWin"

# -----------------------------
# 5) Start services
# -----------------------------
Write-Host "`n[2/3] Starting services..." -ForegroundColor Yellow

if (-not $SkipApi) {
    Start-WslPwshWindow `
        -Title "SKA API (WSL)" `
        -WslRepo $WslRepo `
        -BashCmd "chmod +x ./logs/start_api.sh 2>/dev/null || true; ./logs/start_api.sh $BackendPort" `
        -LogHint "$LogsDirWin\api_*.log"
    Write-Host "  - API launched (new window)" -ForegroundColor Gray
} else {
    Write-Host "  - API skipped" -ForegroundColor Gray
}

if (-not $SkipWorker) {
    Start-WslPwshWindow `
        -Title "SKA WORKER (WSL)" `
        -WslRepo $WslRepo `
        -BashCmd "chmod +x ./logs/start_worker.sh 2>/dev/null || true; ./logs/start_worker.sh" `
        -LogHint "$LogsDirWin\worker_*.log"
    Write-Host "  - Worker launched (new window)" -ForegroundColor Gray
} else {
    Write-Host "  - Worker skipped" -ForegroundColor Gray
}

if (-not $SkipFrontend) {
    if (Test-Path $FrontendDir) {
        Write-Host "  - Launching frontend (npm run dev)..." -ForegroundColor Gray
        Start-Process powershell -WorkingDirectory $FrontendDir -ArgumentList @(
            "-NoExit",
            "-NoProfile",
            "-Command",
            "npm run dev"
        )
    } else {
        Write-Warning "Frontend folder not found: $FrontendDir"
    }
} else {
    Write-Host "  - Frontend skipped" -ForegroundColor Gray
}

# -----------------------------
# 6) Finalize
# -----------------------------
Write-Host "`n[3/3] Done." -ForegroundColor Green

if (-not $SkipBrowser) {
    Write-Host "  Opening browser in $BrowserDelaySeconds seconds..." -ForegroundColor Gray
    Start-Sleep -Seconds $BrowserDelaySeconds
    Start-Process $LaunchUrl
} else {
    Write-Host "  Browser launch skipped" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Quick check (backend ready HTTP probe):" -ForegroundColor Gray
Invoke-WslBackendProbe -Port $BackendPort -TimeoutSeconds $BackendProbeTimeoutSeconds | Out-Host