#!/usr/bin/env python3
"""
=============================================================================
🚀 ABSTRACT WIKI ARCHITECT - UNIFIED COMMANDER (v2.2)
=============================================================================
The single entry point for all developer operations.

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
import platform
from pathlib import Path

# --- CONFIGURATION ---
ROOT_DIR = Path(__file__).parent.resolve()

# [FIX] Robust venv detection
VENV_BIN = ROOT_DIR / "venv" / "bin"
VENV_PYTHON = VENV_BIN / "python"

GF_BUILDER = ROOT_DIR / "builder" / "orchestrator.py"
INDEXER = ROOT_DIR / "tools" / "everything_matrix" / "build_index.py"

# -----------------------------------------------------------------------------
# [FIX] GENERATED DIRECTORY RECONCILIATION
#
# The codebase historically used BOTH:
#   - generated/src          (what builder/orchestrator uses)
#   - gf/generated/src       (what some generators/tools wrote into)
#
# This commander makes generated/src canonical, while keeping gf/generated/src
# supported via symlink (best) or one-way sync fallback (Windows-mounted FS).
# -----------------------------------------------------------------------------
CANON_GENERATED_ROOT = ROOT_DIR / "generated"
LEGACY_GENERATED_ROOT = ROOT_DIR / "gf" / "generated"

CANON_GENERATED_DIR = CANON_GENERATED_ROOT / "src"          # canonical
LEGACY_GENERATED_DIR = LEGACY_GENERATED_ROOT / "src"        # legacy

# Use canonical in the rest of this file
GENERATED_DIR = CANON_GENERATED_DIR

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


def is_wsl():
    """Detects if we are running in Windows Subsystem for Linux."""
    if platform.system() == "Linux":
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return True
        except Exception:
            pass
    return False


def run_cmd(cmd, cwd=ROOT_DIR, check=True, capture=False):
    """Runs a shell command safely."""
    env = os.environ.copy()
    env["PATH"] = f"{str(VENV_BIN)}:{env.get('PATH', '')}"

    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=env
    )
    return result


def _safe_symlink(link_path: Path, target_path: Path) -> bool:
    """
    Try to create link_path -> target_path symlink.
    Returns True if created (or already correct), False otherwise.
    """
    try:
        if link_path.exists() or link_path.is_symlink():
            # If it already exists, leave it alone.
            return True
        link_path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(str(target_path), str(link_path), target_is_directory=True)
        return True
    except Exception:
        return False


def _sync_generated_src(src_dir: Path, dst_dir: Path) -> int:
    """
    One-way sync for generated artifacts.
    Copies a small set of relevant file types, only if missing or newer.
    Returns number of files copied.
    """
    if not src_dir.exists():
        return 0

    copied = 0
    dst_dir.mkdir(parents=True, exist_ok=True)

    allow_suffix = {".gf", ".gfo", ".pgf", ".json", ".log"}

    for p in src_dir.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in allow_suffix:
            continue

        rel = p.relative_to(src_dir)
        out = dst_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)

        if (not out.exists()) or (p.stat().st_mtime > out.stat().st_mtime + 1e-6):
            shutil.copy2(p, out)
            copied += 1

    return copied


def reconcile_generated_dirs(verbose=False):
    """
    Ensure:
      - generated/src exists (canonical)
      - gf/generated/src exists (legacy)
      - best effort to make both point to the same backing store via symlink
      - fallback: sync legacy -> canonical (because AI generator often writes legacy)
    """
    # Ensure both roots/src exist (as directories at minimum)
    LEGACY_GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    CANON_GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # Best case: symlink generated -> gf/generated (preferred backing)
    # This keeps existing tools that write into gf/generated working without changes.
    linked = _safe_symlink(CANON_GENERATED_ROOT, LEGACY_GENERATED_ROOT)

    # Some Windows-mounted directories (/mnt/c/...) may not support symlinks reliably.
    # If we couldn't link, fallback to syncing legacy -> canonical before builds/tests.
    if not linked:
        copied = _sync_generated_src(LEGACY_GENERATED_DIR, CANON_GENERATED_DIR)
        if verbose and copied:
            log(f"    🔁 Synced {copied} files: gf/generated/src -> generated/src", Colors.WARNING)

    # Also ensure the reverse legacy path exists; if someone created canonical first,
    # keep legacy usable (but do NOT overwrite canonical).
    if not LEGACY_GENERATED_ROOT.exists():
        _safe_symlink(LEGACY_GENERATED_ROOT, CANON_GENERATED_ROOT)

    if verbose:
        try:
            canon = CANON_GENERATED_DIR.resolve()
            legacy = LEGACY_GENERATED_DIR.resolve()
            if canon == legacy:
                log(f"    ✅ Generated dirs unified: {CANON_GENERATED_DIR.relative_to(ROOT_DIR)} == {LEGACY_GENERATED_DIR.relative_to(ROOT_DIR)}", Colors.GREEN)
            else:
                log(f"    ⚠️  Generated dirs distinct:", Colors.WARNING)
                log(f"       - {CANON_GENERATED_DIR} -> {canon}", Colors.WARNING)
                log(f"       - {LEGACY_GENERATED_DIR} -> {legacy}", Colors.WARNING)
        except Exception:
            pass


# --- COMMANDS ---

def check_env():
    """Pre-flight checks for Docker, Redis, and GF."""
    log("\n[1/5] 🏥 Health Check", Colors.HEADER)

    # 1. Docker
    try:
        run_cmd("docker info", capture=True)
        log("    ✅ Docker is running.", Colors.GREEN)
    except Exception:
        log("    ❌ Docker is NOT running. Please start Docker Desktop.", Colors.FAIL)
        sys.exit(1)

    # 2. Redis
    try:
        res = run_cmd("docker ps -q -f name=aw_redis", capture=True)
        if res.stdout.strip():
            log("    ✅ Redis container is active.", Colors.GREEN)
        else:
            log("    ⚠️  Redis container not found/running. Starting...", Colors.WARNING)
            run_cmd("docker run -d -p 6379:6379 --name aw_redis redis:alpine")
            log("    ✅ Redis started.", Colors.GREEN)
    except Exception as e:
        log(f"    ❌ Redis check failed: {e}", Colors.FAIL)

    # 3. GF Binary
    try:
        run_cmd("gf --version", capture=True)
        log("    ✅ GF compiler found.", Colors.GREEN)
    except Exception:
        log("    ❌ 'gf' binary not found in PATH.", Colors.FAIL)
        sys.exit(1)


def clean_artifacts():
    """Cleanup of generated/build artifacts (handles both generated/src and gf/generated/src)."""
    reconcile_generated_dirs(verbose=False)

    log("\n🧹 Cleaning Artifacts...", Colors.WARNING)

    # Known zombie subdirs + logs + compiled artifacts
    targets = []

    # Handle known zombie language folders in BOTH possible generated locations
    for base in (CANON_GENERATED_DIR, LEGACY_GENERATED_DIR):
        targets.extend([
            base / "bul",
            base / "pol",
        ])

    targets.extend([
        BUILD_LOGS,
        ROOT_DIR / "gf" / "AbstractWiki.gfo",
    ])

    for target in targets:
        if target.exists():
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                log(f"    🗑️  Deleted: {target.relative_to(ROOT_DIR)}")
            except Exception as e:
                log(f"    ⚠️  Failed to delete {target}: {e}", Colors.WARNING)

    log("    ✅ Clean complete.", Colors.GREEN)


def build_system(clean=False, parallel=None):
    """The Build Pipeline."""
    reconcile_generated_dirs(verbose=True)

    if clean:
        clean_artifacts()

    log("\n[2/5] 🧠 Indexing Knowledge Layer", Colors.HEADER)
    cmd_idx = f"{VENV_PYTHON} {INDEXER}"
    try:
        run_cmd(cmd_idx)
    except Exception:
        log("❌ Indexing Failed.", Colors.FAIL)
        sys.exit(1)

    log("\n[3/5] 🏗️  Compiling Grammar Layer", Colors.HEADER)
    cmd_build = f"{VENV_PYTHON} {GF_BUILDER}"
    try:
        run_cmd(cmd_build, cwd=ROOT_DIR / "gf")
    except Exception:
        log("❌ Compilation Failed.", Colors.FAIL)
        sys.exit(1)


def kill_stale_processes():
    """Kills old uvicorn/arq processes to free ports."""
    log("\n[4/5] 🔫 Process Cleanup", Colors.HEADER)
    subprocess.run("pkill -f uvicorn || true", shell=True)
    subprocess.run("pkill -f arq || true", shell=True)
    log("    ✅ Port 8000 freed.", Colors.GREEN)


def start_services():
    """Launches API and Worker."""
    log("\n[5/5] 🚀 Launching Services", Colors.HEADER)

    api_cmd = f"cd {ROOT_DIR} && venv/bin/uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload"
    worker_cmd = f"cd {ROOT_DIR} && venv/bin/arq app.workers.worker.WorkerSettings --watch app"

    if is_wsl():
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "wsl", "bash", "-c",
                 f"{api_cmd}; echo '❌ API CRASHED'; exec bash"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            log("    👉 API Window Spawned.", Colors.CYAN)

            subprocess.Popen(
                ["cmd.exe", "/c", "start", "wsl", "bash", "-c",
                 f"{worker_cmd}; echo '❌ WORKER CRASHED'; exec bash"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            log("    👉 Worker Window Spawned.", Colors.CYAN)

            log("\n✅ SYSTEM ONLINE!", Colors.GREEN)
            log("    🗺️  Docs: http://localhost:8000/docs", Colors.BOLD)

        except FileNotFoundError:
            log("    ⚠️  'cmd.exe' not found despite WSL check.", Colors.WARNING)
            _print_manual_commands(api_cmd, worker_cmd)
    else:
        log("    🐧 Native Linux Detected (No GUI spawning)", Colors.BLUE)
        _print_manual_commands(api_cmd, worker_cmd)


def _print_manual_commands(api_cmd, worker_cmd):
    log("\n    Please run these in separate terminals:", Colors.WARNING)
    log(f"    [Terminal 1] {api_cmd}", Colors.CYAN)
    log(f"    [Terminal 2] {worker_cmd}", Colors.CYAN)


def generate_missing(lang_code=None):
    """
    Decoupled generation command.
    Calls the AI or Factory to generate missing grammars.
    """
    reconcile_generated_dirs(verbose=True)

    log("\n🎨 Generating Missing Grammars", Colors.HEADER)

    cmd = f"{VENV_PYTHON} -m ai_services.architect"
    if lang_code:
        cmd += f" --lang {lang_code}"
    else:
        cmd += " --missing"

    try:
        run_cmd(cmd)
        # After generation, ensure builder (generated/src) sees new files even if
        # generator wrote into gf/generated/src on a filesystem that can't symlink.
        copied = _sync_generated_src(LEGACY_GENERATED_DIR, CANON_GENERATED_DIR)
        if copied:
            log(f"    🔁 Synced {copied} files into generated/src", Colors.WARNING)
        log("    ✅ Generation complete.", Colors.GREEN)
    except Exception:
        log("    ❌ Generation failed.", Colors.FAIL)


def doctor():
    """System Diagnostic Tool."""
    reconcile_generated_dirs(verbose=True)

    log("\n🩺 Running Doctor...", Colors.HEADER)

    log(f"    📂 Root: {ROOT_DIR}")
    if not (ROOT_DIR / "gf-rgl").exists():
        log("    ❌ gf-rgl/ folder missing! Run setup.", Colors.FAIL)
    else:
        log("    ✅ gf-rgl/ found.", Colors.GREEN)

    config_file = ROOT_DIR / "app" / "shared" / "config.py"
    if not config_file.exists():
        log("    ❌ app/shared/config.py missing.", Colors.FAIL)
    else:
        log("    ✅ config.py found.", Colors.GREEN)

    # Check generated files in BOTH locations (canonical + legacy)
    zombies = []
    for base in (CANON_GENERATED_DIR, LEGACY_GENERATED_DIR):
        if base.exists():
            zombies.extend(base.glob("**/Wiki*.gf"))

    if zombies:
        log(f"    ⚠️  Found {len(zombies)} generated files across generated/src and gf/generated/src.", Colors.WARNING)
        log("       Run 'python manage.py clean' if you need a full reset.", Colors.WARNING)

    log("    ✅ Doctor complete.", Colors.GREEN)


# --- MAIN ---

def main():
    parser = argparse.ArgumentParser(description="Abstract Wiki Architect Commander")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("start", help="Full Launch: Check, Build, Run")

    build_parser = subparsers.add_parser("build", help="Compile grammars")
    build_parser.add_argument("--clean", action="store_true", help="Clean artifacts first")
    build_parser.add_argument("--parallel", type=int, default=None, help="Number of CPU cores")

    subparsers.add_parser("clean", help="Remove generated artifacts")

    gen_parser = subparsers.add_parser("generate", help="Generate missing grammars via AI/Factory")
    gen_parser.add_argument("--lang", type=str, help="Specific ISO code")
    gen_parser.add_argument("--missing", action="store_true", help="Generate all missing")

    subparsers.add_parser("doctor", help="Run diagnostics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "start":
        check_env()
        kill_stale_processes()
        build_system(clean=False, parallel=None)
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
