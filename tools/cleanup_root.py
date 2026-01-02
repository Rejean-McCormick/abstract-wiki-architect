# tools/cleanup_root.py
import os
import sys
import shutil
import time
import argparse
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Set

# ==============================================================================
# 🧹 ABSTRACT WIKI ROOT CLEANER (v2.0)
# ==============================================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

# Safety: Only operate on these exact file patterns in the root directory
TARGET_PATTERNS = [
    "Wiki*.gf",       # Generated grammar files
    "*.pgf",          # Compiled binaries (should be in gf/)
    "*.tmp",          # Temp files
    "*.log",          # Logs (should be in logs/)
    "*.gfo",          # GF object files
    ".coverage",      # Test coverage
    "junit.xml"       # Test reports (should be in data/reports/)
]

# Safety: Recursive cleanup targets (directories)
RECURSIVE_CLEAN_TARGETS = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "htmlcov",
    "dist",
    "build"
]

# Safety: Never touch these, even if they match patterns
PROTECTED_FILES = {
    "manage.py",
    "pyproject.toml", 
    "README.md",
    ".gitignore",
    ".env",
    "docker-compose.yml"
}

COLORS = {
    "HEADER": "\033[95m", "BLUE": "\033[94m", "CYAN": "\033[96m",
    "GREEN": "\033[92m", "WARN": "\033[93m", "FAIL": "\033[91m", "RESET": "\033[0m"
}

def print_c(color, text):
    """Print colored text to stdout if connected to a TTY."""
    if sys.stdout.isatty():
        print(f"{COLORS.get(color, '')}{text}{COLORS['RESET']}")
    else:
        print(text)

def get_rel_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR))
    except ValueError:
        return str(path)

def scan_root_artifacts() -> Dict[str, List[Path]]:
    """Scans the repository root for files that shouldn't be there."""
    artifacts = {
        "move_to_gf": [],
        "delete_files": [],
        "delete_dirs": []
    }

    # 1. Scan Root Files
    for pattern in TARGET_PATTERNS:
        for match in ROOT_DIR.glob(pattern):
            if match.name in PROTECTED_FILES:
                continue
            
            # Logic: .gf files -> move to gf/, others -> delete
            if match.suffix == ".gf" or match.suffix == ".pgf":
                artifacts["move_to_gf"].append(match)
            else:
                artifacts["delete_files"].append(match)

    # 2. Scan Recursive Directories (Safety: Enforce ROOT_DIR boundary)
    for pattern in RECURSIVE_CLEAN_TARGETS:
        for match in ROOT_DIR.rglob(pattern):
            if match.is_dir():
                artifacts["delete_dirs"].append(match)

    return artifacts

def perform_cleanup(dry_run: bool, verbose: bool, json_output: bool) -> int:
    start_time = time.time()
    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")
    
    if not json_output:
        print_c("HEADER", f"=== ROOT CLEANUP UTILITY ===")
        print(f"Trace ID: {trace_id}")
        print(f"Root:     {ROOT_DIR}")
        print(f"Mode:     {'DRY RUN (Safe)' if dry_run else 'LIVE EXECUTION'}")
        print("-" * 40)

    # 1. Plan
    plan = scan_root_artifacts()
    
    total_moves = len(plan["move_to_gf"])
    total_deletes = len(plan["delete_files"]) + len(plan["delete_dirs"])
    total_actions = total_moves + total_deletes

    if not json_output:
        print_c("CYAN", f"🔍 Scan Complete. Found {total_actions} artifacts.")
        
        if verbose or dry_run:
            if plan["move_to_gf"]:
                print_c("BLUE", "\n[PLAN] Move to 'gf/' folder:")
                for p in plan["move_to_gf"]:
                    print(f"  -> {get_rel_path(p)}")
            
            if plan["delete_files"]:
                print_c("WARN", "\n[PLAN] Delete Files:")
                for p in plan["delete_files"]:
                    print(f"  X  {get_rel_path(p)}")

            if plan["delete_dirs"]:
                print_c("WARN", "\n[PLAN] Delete Directories (Recursive):")
                for p in plan["delete_dirs"]:
                    print(f"  X  {get_rel_path(p)}")
        print("")

    if dry_run:
        if json_output:
            print(json.dumps({
                "status": "planned",
                "plan": {k: [str(p) for p in v] for k, v in plan.items()},
                "counts": {"moves": total_moves, "deletes": total_deletes}
            }, indent=2))
        else:
            print_c("GREEN", "✅ Dry run complete. No changes made.")
        return 0

    # 2. Execute
    results = {
        "moved": [],
        "deleted": [],
        "errors": []
    }

    # Execute Moves
    gf_target_dir = ROOT_DIR / "gf"
    if not gf_target_dir.exists():
        gf_target_dir.mkdir()

    for p in plan["move_to_gf"]:
        try:
            dest = gf_target_dir / p.name
            shutil.move(str(p), str(dest))
            results["moved"].append(str(p))
            if verbose: print(f"Moved: {p.name} -> gf/")
        except Exception as e:
            results["errors"].append({"file": str(p), "error": str(e)})

    # Execute File Deletes
    for p in plan["delete_files"]:
        try:
            p.unlink()
            results["deleted"].append(str(p))
            if verbose: print(f"Deleted: {p.name}")
        except Exception as e:
            results["errors"].append({"file": str(p), "error": str(e)})

    # Execute Dir Deletes
    for p in plan["delete_dirs"]:
        try:
            shutil.rmtree(p)
            results["deleted"].append(str(p))
            if verbose: print(f"Removed tree: {get_rel_path(p)}")
        except Exception as e:
            results["errors"].append({"path": str(p), "error": str(e)})

    duration = time.time() - start_time

    # 3. Report
    if json_output:
        print(json.dumps({
            "status": "success" if not results["errors"] else "partial_failure",
            "duration_sec": duration,
            "results": results
        }, indent=2))
    else:
        print("-" * 40)
        print_c("GREEN" if not results["errors"] else "WARN", 
                f"Done in {duration:.2f}s")
        print(f"Moved:   {len(results['moved'])}")
        print(f"Deleted: {len(results['deleted'])}")
        
        if results["errors"]:
            print_c("FAIL", f"\nErrors encountered: {len(results['errors'])}")
            for e in results["errors"]:
                print(f"  ! {e}")

    return 1 if results["errors"] else 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup repository root artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing changes")
    parser.add_argument("--verbose", action="store_true", help="Print detailed operations")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    
    args = parser.parse_args()
    
    sys.exit(perform_cleanup(args.dry_run, args.verbose, args.json))