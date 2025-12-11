import os
import json
import subprocess
import glob
from . import config

# --- Configuration ---
LOG_DIR = 'build_logs'
# This report is critical for the AI Surgeon to know what to fix
FAILURE_REPORT = os.path.join("data", "reports", "build_failures.json")

def get_sandboxed_env():
    """
    Creates a clean environment for the compiler.
    Removes 'GF_LIB_PATH' to ensure we only use the local RGL version.
    """
    env = os.environ.copy()
    if "GF_LIB_PATH" in env:
        del env["GF_LIB_PATH"]
    return env

def setup_paths():
    """
    Constructs the exact include path string for GF.
    Combines Core RGL + Family Folders + Specific Language Paths.
    """
    if not os.path.exists(config.RGL_PATHS_FILE):
        print(f"❌ Error: Paths file not found at {config.RGL_PATHS_FILE}")
        return None

    abs_rgl_base = os.path.abspath(config.RGL_BASE)
    
    with open(config.RGL_PATHS_FILE, 'r') as f:
        path_data = json.load(f)

    # 1. Base RGL Paths (API, Abstract, Common, Prelude)
    include_paths = {
        abs_rgl_base, 
        os.path.join(abs_rgl_base, 'api'),
        os.path.join(abs_rgl_base, 'abstract'),
        os.path.join(abs_rgl_base, 'common'),
        os.path.join(abs_rgl_base, 'prelude')
    }

    # 2. Shared Families (Romance, Germanic, etc.)
    for family in config.FAMILY_FOLDERS:
        full_path = os.path.join(abs_rgl_base, family)
        if os.path.exists(full_path):
            include_paths.add(full_path)

    # 3. Specific Language Folders
    for filename in path_data.values():
        folder_name = os.path.dirname(filename)
        full_path = os.path.join(abs_rgl_base, folder_name)
        include_paths.add(full_path)

    return ":".join(include_paths)

def run():
    print(f"🚀 Starting Wiki PGF Compilation (Sandboxed)...")
    
    if not os.path.exists(config.GF_DIR):
        print(f"❌ Error: Directory '{config.GF_DIR}' not found.")
        return False

    path_arg = setup_paths()
    if not path_arg: return False
    
    # Prepare Environment
    sandbox_env = get_sandboxed_env()
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(FAILURE_REPORT), exist_ok=True)
    
    # Identify Candidates
    all_files = glob.glob(os.path.join(config.GF_DIR, "Wiki*.gf"))
    concrete_files = sorted([os.path.basename(f) for f in all_files if "Wiki.gf" not in f])
    
    successful_files = []
    failed_languages = {} # Stores data for the AI Surgeon
    
    print(f"--- Phase 1: Individual Verification ({len(concrete_files)} languages) ---")

    # 1. Compile Abstract (Critical)
    try:
        subprocess.run(
            ["gf", "-make", "-path", path_arg, "Wiki.gf"], 
            cwd=config.GF_DIR, env=sandbox_env, check=True, 
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        print("✔ Abstract Wiki.gf compiled successfully.")
    except subprocess.CalledProcessError as e:
        print("❌ CRITICAL: Abstract Wiki.gf failed.")
        print(e.stderr.decode("utf-8"))
        return False

    # 2. Compile Concretes (Robust Loop)
    for filename in concrete_files:
        lang_code = filename.replace("Wiki", "").replace(".gf", "")
        
        try:
            # We compile one by one to isolate failures
            subprocess.run(
                ["gf", "-make", "-path", path_arg, filename],
                cwd=config.GF_DIR, env=sandbox_env, check=True, 
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            print(f"✔ {lang_code:<10} [OK]")
            successful_files.append(filename)
            
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode("utf-8", errors="replace").strip()
            
            # Formatted summary for console
            summary = "\n   ".join(err_msg.splitlines()[-2:])
            print(f"❌ {lang_code:<10} [FAILED] -> {summary}")
            
            # Record for AI Surgeon - Uses FULL error message
            failed_languages[lang_code] = {
                "file": filename,
                "reason": err_msg # Give full error context to AI
            }
            
            # Archive full log
            with open(os.path.join(LOG_DIR, f"error_{lang_code}.txt"), "w", encoding="utf-8") as log:
                log.write(err_msg)

    # 3. Generate Failure Report
    # This is the "Medical Chart" the Surgeon will read
    with open(FAILURE_REPORT, "w", encoding="utf-8") as f:
        json.dump(failed_languages, f, indent=2)
    print(f"📝 Failure report saved to {FAILURE_REPORT}")

    print("-" * 60)
    print(f"Summary: {len(successful_files)} Passed, {len(failed_languages)} Failed.")

    # 4. Final Link
    if not successful_files:
        print("\n❌ No languages compiled successfully. Exiting.")
        return False

    print(f"\n--- Phase 2: Linking Final PGF ---")
    final_cmd = ["gf", "-make", "-path", path_arg, "Wiki.gf"] + successful_files
    
    try:
        subprocess.run(
            final_cmd, cwd=config.GF_DIR, env=sandbox_env, check=True
        )
        print(f"\n✅ SUCCESS: {os.path.join(config.GF_DIR, 'Wiki.pgf')} created.")
        return True
    except subprocess.CalledProcessError:
        print("\n❌ FAILURE during final linking.")
        return False