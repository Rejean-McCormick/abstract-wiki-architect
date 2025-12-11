import json
import os
import subprocess
import glob
import sys

# --- Configuration ---
GF_DIR = "gf"                 # Directory containing your grammar source files
RGL_PATHS_FILE = 'rgl_paths.json'
RGL_BASE = 'gf-rgl/src'       # Relative to project root
LOG_DIR = 'build_logs'

# Explicitly include shared family folders to prevent missing module errors
FAMILY_FOLDERS = [
    'romance',      # Cat, Fre, Ita, Por, Ron, Spa
    'scandinavian', # Dan, Nor, Swe
    'germanic',     # Afr, Dut, Ger, Eng
    'uralic',       # Est, Fin
    'slavic',       # Bul, Pol, Rus
    'baltic',       # Lav, Lit
    'hindustani',   # Hin, Urd
    'arabic',       # Shared definitions
    'turkic'        # Tur
]

def setup_paths():
    """
    Constructs the GF library path string using ABSOLUTE paths.
    This ensures dependencies are found regardless of where the command is run.
    """
    if not os.path.exists(RGL_PATHS_FILE):
        print("❌ Error: rgl_paths.json not found. Run 'generate_path_map.py' first.")
        return None

    # Convert RGL_BASE to Absolute Path
    abs_rgl_base = os.path.abspath(RGL_BASE)

    with open(RGL_PATHS_FILE, 'r') as f:
        path_data = json.load(f)

    # 1. Base paths (Absolute)
    include_paths = {
        abs_rgl_base, 
        os.path.join(abs_rgl_base, 'api'),
        os.path.join(abs_rgl_base, 'abstract'),
        os.path.join(abs_rgl_base, 'common'),
        os.path.join(abs_rgl_base, 'prelude')
    }

    # 2. Add Family paths (Critical for inheritance)
    for family in FAMILY_FOLDERS:
        full_path = os.path.join(abs_rgl_base, family)
        if os.path.exists(full_path):
            include_paths.add(full_path)

    # 3. Add specific language folders from the mapping
    for filename in path_data.values():
        # filename from JSON is relative (e.g. "afrikaans/CatAfr.gf")
        # We need the directory relative to RGL_BASE
        folder_name = os.path.dirname(filename)
        full_path = os.path.join(abs_rgl_base, folder_name)
        include_paths.add(full_path)

    # Return paths joined by the OS separator (semicolon for Windows, colon for Mac/Linux if needed, but GF usually accepts :)
    # Python on Windows usually handles ':' in arguments fine for GF, but let's be safe.
    return ":".join(include_paths)

def compile_robustly():
    print(f"🚀 Starting Wiki PGF Compilation (V1 Explicit)...")
    
    # 0. Check Environment
    if not os.path.exists(GF_DIR):
        print(f"❌ Error: Directory '{GF_DIR}' not found.")
        return

    path_arg = setup_paths()
    if not path_arg:
        return

    os.makedirs(LOG_DIR, exist_ok=True)

    # 1. Scan for Source Files in GF_DIR
    # We look for gf/Wiki*.gf
    all_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    
    # We need just the filenames for the command (e.g. "WikiEng.gf") 
    # because we will run the command inside the GF_DIR.
    concrete_files = [os.path.basename(f) for f in all_files if "Wiki.gf" not in f]
    
    successful_files = []
    
    print(f"--- Phase 1: Individual Compilation Check ({len(concrete_files)} languages) ---")

    # 2. Compile Abstract Grammar (Wiki.gf)
    try:
        subprocess.run(
            ["gf", "-make", "-path", path_arg, "Wiki.gf"], 
            cwd=GF_DIR,  # <--- CRITICAL: Run inside gf/ folder
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.PIPE
        )
        print("✔ Abstract Wiki.gf compiled successfully.")
    except subprocess.CalledProcessError as e:
        print("❌ CRITICAL: Abstract Wiki.gf failed. Aborting.")
        print(e.stderr.decode("utf-8"))
        return

    # 3. Test Each Concrete Grammar
    for filename in concrete_files:
        lang_code = filename.replace("Wiki", "").replace(".gf", "")
        
        try:
            # Individual dry-run to check for errors
            subprocess.run(
                ["gf", "-make", "-path", path_arg, filename],
                cwd=GF_DIR,  # <--- Run inside gf/
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            print(f"✔ {lang_code}")
            successful_files.append(filename)
            
        except subprocess.CalledProcessError as e:
            print(f"✘ {lang_code} (FAILED - see logs)")
            log_path = os.path.join(LOG_DIR, f"error_{lang_code}.txt")
            with open(log_path, "w", encoding="utf-8") as log:
                log.write(f"File: {filename}\n")
                log.write(f"Context: cwd={GF_DIR}\n")
                log.write("-" * 40 + "\n")
                log.write(e.stderr.decode("utf-8", errors="replace"))

    # 4. Final Build
    if not successful_files:
        print("\n❌ No languages compiled successfully. Exiting.")
        return

    print(f"\n--- Phase 2: Building Final PGF with {len(successful_files)} languages ---")
    
    # We compile 'Wiki.gf' + all valid concrete syntaxes
    final_cmd = ["gf", "-make", "-path", path_arg, "Wiki.gf"] + successful_files
    
    try:
        subprocess.run(
            final_cmd, 
            cwd=GF_DIR, # <--- Run inside gf/
            check=True
        )
        print(f"\n✅ SUCCESS: {os.path.join(GF_DIR, 'Wiki.pgf')} created.")
        print(f"   Included: {len(successful_files)} languages.")
    except subprocess.CalledProcessError:
        print("\n❌ FAILURE during final linking.")

if __name__ == "__main__":
    compile_robustly()