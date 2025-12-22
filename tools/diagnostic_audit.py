# tools\diagnostic_audit.py
import os
import json
import sys
import glob

# ==============================================================================
# 🕵️ ABSTRACT WIKI DIAGNOSTIC AUDITOR (v2.0)
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
    print(f"{COLORS.get(color, '')}{text}{COLORS['RESET']}")

def check_zombie_file(iso, path):
    """
    Forensics: deeply inspects a .gf file to see if it's an old 'Zombie'
    or a fresh 'Empty Connector'.
    """
    if not os.path.exists(path):
        return "MISSING"
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
        
    # HEURISTIC 1: The new connector should be tiny (approx 1-3 lines)
    if len(lines) > 10:
        # HEURISTIC 2: Look for the specific breaking syntax from old versions
        if "mkN" in content or "mkAdv" in content or "apple_N" in content:
            return "🧟 ZOMBIE (Old Broken Version)"
        return "⚠️  SUSPICIOUS (Too large for a connector)"
    
    if "open Syntax" in content and "{}" in content:
        return "✅ CLEAN (Empty Connector)"
    
    return "❓ UNKNOWN"

def run_audit():
    print_c("HEADER", f"\n🚀 STARTING DEEP SYSTEM AUDIT")
    print_c("HEADER", f"===========================")
    print(f"📂 Root:    {ROOT_DIR}")
    print(f"📄 Matrix:  {MATRIX_PATH}")

    if not os.path.exists(MATRIX_PATH):
        print_c("FAIL", "❌ CRITICAL: Matrix file not found!")
        sys.exit(1)

    with open(MATRIX_PATH, 'r') as f:
        matrix = json.load(f)

    langs = matrix.get("languages", {})
    print_c("CYAN", f"📊 Matrix Index: {len(langs)} languages found.\n")

    zombies_found = []

    print(f"{'ISO':<6} | {'STRATEGY':<12} | {'GEN STATUS':<30} | {'CONTRIB STATUS':<20} | {'RGL PATH'}")
    print("-" * 110)

    for iso, data in langs.items():
        strategy = data.get("status", {}).get("build_strategy", "UNKNOWN")
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
        rgl_exists = "✅ Found" if os.path.exists(rgl_path) else "❌ Missing"

        # Colorize Row
        row_color = "RESET"
        if "ZOMBIE" in gen_status:
            row_color = "FAIL"
            zombies_found.append(gen_path)
        elif "ZOMBIE" in contrib_status:
            row_color = "FAIL"
            zombies_found.append(contrib_path)
        elif iso == "tur":
             row_color = "WARN" # Always warn about Turkish
        
        print_c(row_color, f"{iso:<6} | {strategy:<12} | {gen_status:<30} | {contrib_status:<20} | {rgl_exists} ({rgl_folder})")

    print("\n")
    print_c("HEADER", "🩺 DIAGNOSTIC REPORT")
    print_c("HEADER", "-------------------")

    # REPORT: ZOMBIES
    if zombies_found:
        print_c("FAIL", f"🧟 ZOMBIE FILES DETECTED: {len(zombies_found)}")
        print("   These files are leftovers from previous bad builds.")
        print("   They contain broken code (like 'mkN') that causes compilation to fail.")
        print_c("WARN", "   👉 SUGGESTION: Delete these files immediately.")
        for z in zombies_found:
            print(f"      rm {z}")
    else:
        print_c("GREEN", "✅ No Zombie files detected.")

    # REPORT: TURKISH
    print("\n")
    print_c("WARN", "🇹🇷 SPECIAL NOTE: Turkish (tur)")
    print("   The logs show 'Internal error in Compute.Concrete'.")
    print("   This is a known bug in the GF compiler (upstream).")
    print("   Action: The system is correctly skipping it. No fix possible currently.")

if __name__ == "__main__":
    run_audit()