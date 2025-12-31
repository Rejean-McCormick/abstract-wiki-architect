<#
.SYNOPSIS
    The "God Mode" Window Manager.
    It cleans up zombie processes and then delegates startup logic to 'manage.py'.
#>

$WSL_PATH = "/mnt/c/MyCode/AbstractWiki/abstract-wiki-architect"
$WIN_PATH = "C:\MyCode\AbstractWiki\abstract-wiki-architect"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   🏗️  ABSTRACT WIKI ARCHITECT - LAUNCHER" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# --- 1. CLEANUP (Powershell Exclusive) ---
# Python scripts running inside WSL cannot easily kill Windows Node processes.
# We do this here to ensure a clean slate.
Write-Host "`n[1/3] 🧹 Cleaning up zombie processes..." -ForegroundColor Yellow

# Kill Windows Frontend
if (Get-Process node -ErrorAction SilentlyContinue) { 
    Stop-Process -Name node -Force -ErrorAction SilentlyContinue
    Write-Host "   - Killed lingering Node/Next.js" -ForegroundColor Gray
}

# Kill WSL Backend (Force kill port 8000)
wsl bash -c "fuser -k 8000/tcp > /dev/null 2>&1 || true"
Write-Host "   - Cleared Port 8000 (WSL)" -ForegroundColor Gray

# --- 2. DELEGATE TO MANAGE.PY (The Commander) ---
# We spawn a single orchestrator window for the backend.
# manage.py 'start' will:
#   1. Run Health Checks
#   2. Build the System
#   3. Spawn its own separate windows for API and Worker

Write-Host "`n[2/3] 🚀 Spawning Services via manage.py..." -ForegroundColor Yellow

# Terminal 1: Backend Orchestrator (Builds & Spawns Sub-windows)
$backendCmd = "cd $WSL_PATH; source venv/bin/activate; python3 manage.py start"
Start-Process wsl.exe -ArgumentList "bash -c '$backendCmd; exec bash'"

# Terminal 2: Frontend (Windows Native)
# We assume standard npm run dev here as it's outside the Python scope
Write-Host "   - Launching Frontend..." -ForegroundColor Gray
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$WIN_PATH\architect_frontend'; npm run dev"

# --- 3. FINALIZE ---
Write-Host "`n[3/3] ✅ Systems Go!" -ForegroundColor Green
Write-Host "   Browser opening in 5 seconds..." -ForegroundColor Gray

Start-Sleep -Seconds 5
Start-Process "http://localhost:3000/abstract_wiki_architect/tools"