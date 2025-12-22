#!/usr/bin/env python3
"""
=============================================================================
🚀 ABSTRACT WIKI ARCHITECT - UNIFIED COMMANDER (v2.0)
=============================================================================
The single entry point for all developer operations.
Replaces fragile PowerShell/Shell scripts with robust Python logic.

Usage:
    python manage.py start       # Daily driver: Check -> Build -> Launch
    python manage.py build       # Compile grammars (supports --clean, --parallel)
    python manage.py clean       # Nuke generated artifacts (Zombie killer)
    python manage.py doctor      # System health check
    python manage.py generate    # AI/Factory generation for missing languages
"""

import os
import sys
import subprocess
import argparse
import shutil
import time
import platform
import json
from pathlib import Path

# --- CONFIGURATION ---
ROOT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = ROOT_DIR / "venv" / "bin" / "python"
GF_BUILDER = ROOT_DIR / "gf" / "build_orchestrator.py"
INDEXER = ROOT_DIR / "tools" / "everything_matrix" / "build_index.py"
ARCHITECT_CLI = ROOT_DIR / "ai_services" / "architect.py" # To be refactored
GENERATED_DIR = ROOT_DIR / "gf" / "generated" / "src"
CONTRIB_DIR = ROOT_DIR / "gf" / "contrib"
BUILD_LOGS = ROOT_DIR / "gf" / "build_logs"

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(msg, color=Colors.ENDC):
    print(f"{color}{msg}{Colors.ENDC}")

def run_cmd(cmd, cwd=ROOT_DIR, check=True, capture=False):
    """Runs a shell command safely."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=str(cwd), 
            shell=True, 
            check=check,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None
        )
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            log(f"❌ Command failed: {cmd}\nError: {e.stderr}", Colors.FAIL)
        raise e

# --- COMMANDS ---

def check_env():
    """Pre-flight checks for Docker, Redis, and GF."""
    log("\n[1/5] 🏥 Health Check", Colors.HEADER)
    
    # 1. Docker
    try:
        run_cmd("docker info", capture=True)
        log("   ✅ Docker is running.", Colors.GREEN)
    except:
        log("   ❌ Docker is NOT running. Please start Docker Desktop.", Colors.FAIL)
        sys.exit(1)

    # 2. Redis
    try:
        # Check if container exists/runs
        res = run_cmd("docker ps -q -f name=aw_redis", capture=True)
        if res.stdout.strip():
            log("   ✅ Redis container is active.", Colors.GREEN)
        else:
            log("   ⚠️  Redis container not found/running. Starting...", Colors.WARNING)
            run_cmd("docker run -d -p 6379:6379 --name aw_redis redis:alpine")
            log("   ✅ Redis started.", Colors.GREEN)
    except Exception as e:
        log(f"   ❌ Redis check failed: {e}", Colors.FAIL)

    # 3. GF Binary
    try:
        run_cmd("gf --version", capture=True)
        log("   ✅ GF compiler found.", Colors.GREEN)
    except:
        log("   ❌ 'gf' binary not found in PATH.", Colors.FAIL)
        sys.exit(1)

def clean_artifacts():
    """Nuclear cleanup of generated files."""
    log("\n🧹 Cleaning Artifacts...", Colors.WARNING)
    
    targets = [
        GENERATED_DIR / "bul", GENERATED_DIR / "pol",  # Known zombies
        CONTRIB_DIR / "bul", CONTRIB_DIR / "pol",      # Known zombies
        BUILD_LOGS,
        ROOT_DIR / "gf" / "AbstractWiki.gfo"
    ]
    
    # Also clean generated src root if needed, but be careful not to delete .keep
    # For now, just specific targets and logs
    
    for target in targets:
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                os.remove(target)
            log(f"   🗑️  Deleted: {target.relative_to(ROOT_DIR)}")
        
    log("   ✅ Clean complete.", Colors.GREEN)

def build_system(clean=False, parallel=None):
    """The Build Pipeline."""
    if clean:
        clean_artifacts()

    log("\n[2/5] 🧠 Indexing Knowledge Layer", Colors.HEADER)
    # Step 1: Indexer
    cmd_idx = f"{VENV_PYTHON} {INDEXER}"
    try:
        run_cmd(cmd_idx)
    except:
        log("❌ Indexing Failed.", Colors.FAIL)
        sys.exit(1)

    log("\n[3/5] 🏗️  Compiling Grammar Layer", Colors.HEADER)
    # Step 2: Builder
    # We pass arguments to the orchestrator if needed (future proofing)
    cmd_build = f"{VENV_PYTHON} {GF_BUILDER}"
    # If we implemented args in build_orchestrator, we would pass --parallel here
    
    try:
        run_cmd(cmd_build, cwd=ROOT_DIR / "gf")
    except:
        log("❌ Compilation Failed.", Colors.FAIL)
        # We don't exit here if we want to allow 'resilience mode', 
        # but for a strict build command, we should probably fail.
        sys.exit(1)

def kill_stale_processes():
    """Kills old uvicorn/arq processes to free ports."""
    log("\n[4/5] 🔫 Process Cleanup", Colors.HEADER)
    # WSL specific pkill
    subprocess.run("pkill -f uvicorn || true", shell=True)
    subprocess.run("pkill -f arq || true", shell=True)
    log("   ✅ Port 8000 freed.", Colors.GREEN)

def start_services():
    """Launches API and Worker in separate visible windows."""
    log("\n[5/5] 🚀 Launching Services", Colors.HEADER)
    
    # We use cmd.exe to pop up windows on Windows via WSL
    # NOTE: This assumes WSL environment
    
    api_cmd = f"cd {ROOT_DIR} && venv/bin/uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload; echo '❌ API CRASHED'; exec bash"
    worker_cmd = f"cd {ROOT_DIR} && venv/bin/arq app.workers.worker.WorkerSettings --watch app; echo '❌ WORKER CRASHED'; exec bash"

    try:
        # Spawn API
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "wsl", "bash", "-c", api_cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log("   👉 API Window Spawned.", Colors.CYAN)

        # Spawn Worker
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "wsl", "bash", "-c", worker_cmd],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        log("   👉 Worker Window Spawned.", Colors.CYAN)
        
        log("\n✅ SYSTEM ONLINE!", Colors.GREEN)
        log(f"   🗺️  Docs: http://localhost:8000/docs", Colors.BOLD)

    except FileNotFoundError:
        log("   ❌ Could not find 'cmd.exe'. Are you running in WSL?", Colors.FAIL)
        # Fallback to background processes? No, let's fail loud.

def generate_missing(lang_code=None):
    """
    Decoupled generation command.
    Calls the AI or Factory to generate missing grammars.
    """
    log("\n🎨 Generating Missing Grammars", Colors.HEADER)
    # This assumes architect.py has a CLI interface (we will add this later)
    # For now, it's a placeholder for the logic we split out.
    
    cmd = f"{VENV_PYTHON} -m ai_services.architect"
    if lang_code:
        cmd += f" --lang {lang_code}"
    else:
        cmd += " --missing" # Generate all missing
        
    try:
        run_cmd(cmd)
        log("   ✅ Generation complete.", Colors.GREEN)
    except:
        log("   ❌ Generation failed.", Colors.FAIL)

def doctor():
    """System Diagnostic Tool."""
    log("\n🩺 Running Doctor...", Colors.HEADER)
    
    # 1. Check Paths
    log(f"   📂 Root: {ROOT_DIR}")
    if not (ROOT_DIR / "gf-rgl").exists():
        log("   ❌ gf-rgl/ folder missing! Run setup.", Colors.FAIL)
    else:
        log("   ✅ gf-rgl/ found.", Colors.GREEN)

    # 2. Check Config
    config_file = ROOT_DIR / "app" / "shared" / "config.py"
    if not config_file.exists():
        log("   ❌ app/shared/config.py missing.", Colors.FAIL)
    else:
        log("   ✅ config.py found.", Colors.GREEN)

    # 3. Check Zombies
    zombies = list(GENERATED_DIR.glob("**/Wiki*.gf"))
    if zombies:
        log(f"   ⚠️  Found {len(zombies)} generated files. Run 'manage.py clean' to reset.", Colors.WARNING)
    
    log("   ✅ Doctor complete.", Colors.GREEN)

# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="Abstract Wiki Architect Commander")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start
    subparsers.add_parser("start", help="Full Launch: Check, Build, Run")
    
    # Build
    build_parser = subparsers.add_parser("build", help="Compile grammars")
    build_parser.add_argument("--clean", action="store_true", help="Clean artifacts first")
    build_parser.add_argument("--parallel", type=int, default=None, help="Number of CPU cores")

    # Clean
    subparsers.add_parser("clean", help="Remove generated artifacts")

    # Generate
    gen_parser = subparsers.add_parser("generate", help="Generate missing grammars via AI/Factory")
    gen_parser.add_argument("--lang", type=str, help="Specific ISO code")
    gen_parser.add_argument("--missing", action="store_true", help="Generate all missing")

    # Doctor
    subparsers.add_parser("doctor", help="Run diagnostics")

    args = parser.parse_args()

    # Default to help
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "start":
        check_env()
        kill_stale_processes()
        build_system(clean=False) # Incremental by default
        start_services()
    
    elif args.command == "build":
        build_system(clean=args.clean, parallel=args.parallel)
    
    elif args.command == "clean":
        clean_artifacts()
    
    elif args.command == "generate":
        generate_missing(args.lang)
    
    elif args.command == "doctor":
        doctor()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n🛑 Aborted by user.", Colors.WARNING)