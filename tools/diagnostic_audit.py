# tools/diagnostic_audit.py
import os
import json
import sys
import glob
import time
import argparse
from typing import Dict, Any, List

# ==============================================================================
# 🕵️ ABSTRACT WIKI DIAGNOSTIC AUDITOR (v2.2)
# ==============================================================================

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATRIX_PATH = os.path.join(ROOT_DIR, "data", "indices", "everything_matrix.json")
GENERATED_DIR = os.path.join(ROOT_DIR, "gf", "generated", "src")
CONTRIB_DIR = os.path.join(ROOT_DIR, "gf", "contrib")
RGL_DIR = os.path.join(ROOT_DIR, "gf-rgl", "src")

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

def check_zombie_file(iso, path):
    """
    Forensics: deeply inspects a .gf file to see if it's an old 'Zombie'
    or a fresh 'Empty Connector'.
    """
    if not os.path.exists(path):
        return "MISSING"
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        return f"ERROR_READING: {str(e)}"
        
    # HEURISTIC 1: The new connector should be tiny (approx 1-3 lines)
    if len(lines) > 10:
        # HEURISTIC 2: Look for the specific breaking syntax from old versions
        if "mkN" in content or "mkAdv" in content or "apple_N" in content:
            return "ZOMBIE_OLD_BROKEN"
        return "SUSPICIOUS_TOO_LARGE"
    
    if "open Syntax" in content and "{}" in content:
        return "CLEAN_EMPTY_CONNECTOR"
    
    return "UNKNOWN_CONTENT"

def run_audit(verbose: bool = False, json_output: bool = False) -> int:
    start_time = time.time()
    
    trace_id = os.environ.get("TOOL_TRACE_ID", "N/A")
    if verbose:
        print(f"START: diagnostic_audit | TraceID: {trace_id}")
        print(f"CWD: {os.getcwd()}")
        print(f"ROOT: {ROOT_DIR}")

    if not os.path.exists(MATRIX_PATH):
        if json_output:
            print(json.dumps({"error": "Matrix file not found", "path": MATRIX_PATH}))
        else:
            print_c("FAIL", "❌ CRITICAL: Matrix file not found!")
        return 1

    with open(MATRIX_PATH, 'r') as f:
        matrix = json.load(f)

    langs = matrix.get("languages", {})
    
    if verbose:
        print(f"Loaded matrix with {len(langs)} languages.")

    zombies_found = []
    suspicious_files = []
    scanned_count = 0
    results = []

    if not json_output:
        print_c("HEADER", f"\n🚀 STARTING DEEP SYSTEM AUDIT")
        print_c("HEADER", f"===========================")
        print_c("CYAN", f"📊 Matrix Index: {len(langs)} languages found.\n")
        print(f"{'ISO':<6} | {'STRATEGY':<12} | {'GEN STATUS':<30} | {'CONTRIB STATUS':<20} | {'RGL PATH'}")
        print("-" * 110)

    for iso, data in langs.items():
        scanned_count += 1
        
        # [FIX] Read from 'verdict' instead of 'status' to match build_index.py schema
        strategy = data.get("verdict", {}).get("build_strategy", "UNKNOWN")
        suffix = iso.capitalize()
        
        # 1. Check Generated File
        gen_path = os.path.join(GENERATED_DIR, iso.lower(), f"Wiki{suffix}.gf")
        gen_status = check_zombie_file(iso, gen_path)
        
        # 2. Check Contrib File (Often where Zombies hide)
        contrib_path = os.path.join(CONTRIB_DIR, iso, f"Wiki{suffix}.gf")
        contrib_status = check_zombie_file(iso, contrib_path)

        # 3. Check RGL
        rgl_folder = data.get("meta", {}).get("folder", "???")
        rgl_path = os.path.join(RGL_DIR, rgl_folder)
        rgl_exists = os.path.exists(rgl_path)
        rgl_str = "Found" if rgl_exists else "Missing"

        # Collect issues
        is_zombie = "ZOMBIE" in gen_status or "ZOMBIE" in contrib_status
        is_suspicious = "SUSPICIOUS" in gen_status or "SUSPICIOUS" in contrib_status
        
        if is_zombie:
            if "ZOMBIE" in gen_status: zombies_found.append(gen_path)
            if "ZOMBIE" in contrib_status: zombies_found.append(contrib_path)
        
        if is_suspicious:
            if "SUSPICIOUS" in gen_status: suspicious_files.append(gen_path)
            if "SUSPICIOUS" in contrib_status: suspicious_files.append(contrib_path)

        # Print row if not JSON output
        if not json_output:
            row_color = "RESET"
            if is_zombie:
                row_color = "FAIL"
            elif is_suspicious:
                row_color = "WARN"
            elif iso == "tur":
                 row_color = "WARN" # Always warn about Turkish known issue
            
            print_c(row_color, f"{iso:<6} | {strategy:<12} | {gen_status:<30} | {contrib_status:<20} | {rgl_str} ({rgl_folder})")
            
        # Collect structured result
        results.append({
            "iso": iso,
            "strategy": strategy,
            "gen_path": gen_path,
            "gen_status": gen_status,
            "contrib_path": contrib_path,
            "contrib_status": contrib_status,
            "rgl_exists": rgl_exists
        })

    duration = time.time() - start_time

    # Summary Generation
    summary = {
        "timestamp": time.time(),
        "duration_sec": duration,
        "scanned_languages": scanned_count,
        "zombies_count": len(zombies_found),
        "suspicious_count": len(suspicious_files),
        "zombie_paths": zombies_found,
        "suspicious_paths": suspicious_files,
        "status": "FAIL" if zombies_found else ("WARN" if suspicious_files else "OK")
    }

    if json_output:
        print(json.dumps(summary, indent=2))
    else:
        print("\n")
        print_c("HEADER", "🩺 DIAGNOSTIC REPORT")
        print_c("HEADER", "-------------------")

        if zombies_found:
            print_c("FAIL", f"🧟 ZOMBIE FILES DETECTED: {len(zombies_found)}")
            print("    These files are leftovers from previous bad builds.")
            print("    They contain broken code (like 'mkN') that causes compilation to fail.")
            print_c("WARN", "    👉 SUGGESTION: Delete these files immediately.")
            for z in zombies_found:
                print(f"      rm {z}")
        else:
            print_c("GREEN", "✅ No Zombie files detected.")

        if suspicious_files and verbose:
            print_c("WARN", f"⚠️  SUSPICIOUS FILES: {len(suspicious_files)}")
            for s in suspicious_files:
                print(f"      {s}")

        # REPORT: TURKISH
        print("\n")
        print_c("WARN", "🇹🇷 SPECIAL NOTE: Turkish (tur)")
        print("    The logs show 'Internal error in Compute.Concrete'.")
        print("    This is a known bug in the GF compiler (upstream).")
        print("    Action: The system is correctly skipping it. No fix possible currently.")
        
        if verbose:
            print(f"Done in {duration:.2f}s")

    # Exit code logic
    if zombies_found:
        return 1
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostic Audit for Abstract Wiki")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    
    sys.exit(run_audit(verbose=args.verbose, json_output=args.json))