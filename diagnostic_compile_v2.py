import os
import subprocess
import glob
import sys
import datetime

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_DIR = "gf-rgl/src"
LOG_FILE = "compile_diagnostic.log"

# Languages known to cause high memory usage or long timeouts
SKIP_LIST = ["Fin", "Est", "Ara", "Heb", "Amh", "Bul"] 
# We skip the ones known to have internal RGL crashes/timeouts

# RGL Shared and Language Paths (Ensure every compiler dependency is found)
RGL_FOLDERS = [
    "api", "abstract", "common", "prelude",
    "romance", "germanic", "scandinavian", "slavic", "uralic", "hindustani", "semitic",
    "afrikaans", "amharic", "arabic", "basque", "bulgarian", "catalan", 
    "chinese", "danish", "dutch", "english", "estonian", "finnish", "french", 
    "german", "greek", "hebrew", "hindi", "hungarian", "icelandic", 
    "indonesian", "italian", "japanese", "korean", "latin", "latvian", 
    "lithuanian", "maltese", "mongolian", "nepali", "norwegian", "persian", 
    "polish", "portuguese", "punjabi", "romanian", "russian", "sindhi", 
    "slovenian", "somali", "spanish", "swahili", "swedish", "thai", "turkish", 
    "urdu", "vietnamese", "xhosa", "yoruba", "zulu"
]

def restore_all():
    """Restores all .SKIP files to their original state."""
    restored_count = 0
    for skip_file in glob.glob(os.path.join(GF_DIR, "*.SKIP")):
        restored_name = skip_file.replace(".SKIP", "")
        os.rename(skip_file, restored_name)
        restored_count += 1
    return restored_count

def run():
    print("🚀 Starting Diagnostic Compilation (V2 - Memory Safe)...")
    
    # 1. Setup Environment
    restore_all() # Restore everything so we can decide what to test
    
    abs_rgl = os.path.abspath(RGL_DIR)
    paths = [os.path.join(abs_rgl, f) for f in RGL_FOLDERS]
    paths = [p for p in paths if os.path.exists(p)] 
    path_str = ":".join(paths)
    
    # 2. Collect files to test
    wiki_files = sorted(glob.glob(os.path.join(GF_DIR, "Wiki*.gf")))
    wiki_files = [f for f in wiki_files if "Wiki.gf" not in f and "WikiI.gf" not in f]
    
    # Filter files based on SKIP_LIST
    files_to_test = []
    for file_path in wiki_files:
        lang_code = os.path.basename(file_path)[4:-3]
        if lang_code not in SKIP_LIST:
            files_to_test.append(file_path)
    
    results = []

    print(f"   Testing {len(files_to_test)} safe languages. ({len(wiki_files) - len(files_to_test)} skipped)")
    
    # 3. Compile Each File Individually
    for i, file_path in enumerate(files_to_test):
        filename = os.path.basename(file_path)
        lang_code = filename[4:-3]
        
        # Display Progress
        sys.stdout.write(f"\r   [{i+1}/{len(files_to_test)}] Testing {lang_code:<5} ({filename})")
        sys.stdout.flush()

        cmd = ["gf", "-make", "-path", path_str, filename]

        try:
            # Shortened timeout for diagnostic mode
            result = subprocess.run(
                cmd, 
                cwd=GF_DIR, 
                capture_output=True, 
                text=True,
                timeout=60 
            )
            
            if result.returncode == 0:
                results.append((filename, "SUCCESS", ""))
            else:
                error_lines = (result.stderr + result.stdout).strip().splitlines()
                summary = "\n".join(error_lines[:10]) # Get a larger chunk of error log
                results.append((filename, "FAILED", summary))

        except subprocess.TimeoutExpired:
            results.append((filename, "TIMEOUT", "Compilation exceeded 60 seconds."))
        except Exception as e:
            results.append((filename, "CRASHED", str(e)))

    # 4. Generate Report
    valid = [r[0] for r in results if r[1] == "SUCCESS"]
    broken = [r for r in results if r[1] != "SUCCESS"]

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"GF WIKI DIAGNOSTIC REPORT (V2)\n")
        f.write(f"Run Date: {datetime.datetime.now()}\n")
        f.write(f"Total Languages Tested: {len(files_to_test)}\n")
        f.write(f"Skipped Languages: {SKIP_LIST}\n")
        f.write(f"Successful: {len(valid)}\n")
        f.write(f"Failed/Timed Out: {len(broken)}\n")
        f.write("="*80 + "\n\n")

        f.write("--- FAILED LANGUAGES ---\n")
        for fname, status, reason in broken:
            f.write(f"\n[❌ {fname} | STATUS: {status}]\n")
            f.write(f"Reason:\n{reason}\n")

        f.write("\n\n--- SUCCESSFUL LANGUAGES ---\n")
        f.write(", ".join(valid) + "\n")
    
    print("\n" + "="*80)
    print(f"✅ Diagnostic Complete. Check {LOG_FILE} for errors.")
    print(f"   Successful: {len(valid)} | Failed: {len(broken)}")
    print("="*80)
    
if __name__ == "__main__":
    run()
    