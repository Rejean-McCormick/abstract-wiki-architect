import json
import os
import subprocess
import glob

# --- Configuration ---
PATHS_FILE = 'rgl_paths.json'
RGL_BASE = 'gf-rgl/src'
LOG_DIR = 'build_logs'

def setup_paths():
    """Generates the GF search path string."""
    if not os.path.exists(PATHS_FILE):
        print("Error: rgl_paths.json not found.")
        return None

    with open(PATHS_FILE, 'r') as f:
        path_data = json.load(f)

    # Base paths including common and prelude
    include_paths = {
        RGL_BASE, 
        os.path.join(RGL_BASE, 'api'),
        os.path.join(RGL_BASE, 'abstract'),
        os.path.join(RGL_BASE, 'common'),
        os.path.join(RGL_BASE, 'prelude')
    }

    # Add specific language folders
    for filename in path_data.values():
        folder_name = os.path.dirname(filename)
        full_path = os.path.join(RGL_BASE, folder_name)
        include_paths.add(full_path)

    return ":".join(include_paths)

def compile_robustly():
    path_arg = setup_paths()
    if not path_arg:
        return

    # Create logs directory
    os.makedirs(LOG_DIR, exist_ok=True)

    # Get all potential grammar files
    all_files = glob.glob("Wiki*.gf")
    concrete_files = [f for f in all_files if f != "Wiki.gf"]
    
    successful_files = []
    
    print(f"--- Phase 1: Individual Compilation Check ({len(concrete_files)} languages) ---")

    # 1. Compile Abstract first
    try:
        subprocess.run(
            ["gf", "-make", "-path", path_arg, "Wiki.gf"], 
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        print("✔ Abstract Wiki.gf compiled successfully.")
    except subprocess.CalledProcessError as e:
        print("CRITICAL: Abstract Wiki.gf failed to compile. Aborting.")
        print(e.stderr.decode())
        return

    # 2. Test each concrete syntax
    for gf_file in concrete_files:
        lang_code = gf_file.replace("Wiki", "").replace(".gf", "")
        
        try:
            # We perform a dry-run compile for this specific file
            result = subprocess.run(
                ["gf", "-make", "-path", path_arg, gf_file],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            print(f"✔ {lang_code}")
            successful_files.append(gf_file)
            
        except subprocess.CalledProcessError as e:
            # On failure: Log it and continue
            print(f"✘ {lang_code} (FAILED - see logs)")
            log_path = os.path.join(LOG_DIR, f"error_{lang_code}.txt")
            with open(log_path, "w", encoding="utf-8") as log:
                log.write(f"Command: gf -make -path ... {gf_file}\n\n")
                log.write(e.stderr.decode())

    # 3. Final Build
    if not successful_files:
        print("\nNo languages compiled successfully.")
        return

    print(f"\n--- Phase 2: Building Final PGF with {len(successful_files)} languages ---")
    
    # We include Wiki.gf + all successful concretes
    final_cmd = ["gf", "-make", "-path", path_arg, "Wiki.gf"] + successful_files
    
    try:
        subprocess.run(final_cmd, check=True)
        print("\nSUCCESS: Wiki.pgf created successfully!")
        print(f"Ignored {len(concrete_files) - len(successful_files)} failed languages (check /{LOG_DIR} for details).")
    except subprocess.CalledProcessError as e:
        print("\nFAILURE during final linking.")

if __name__ == "__main__":
    compile_robustly()