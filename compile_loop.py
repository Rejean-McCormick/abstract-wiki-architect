import os
import subprocess
import glob
import re
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_DIR = "gf-rgl/src"

# CRITICAL FIX: Added shared family folders (romance, germanic, etc.)
RGL_FOLDERS = [
    # Core
    "api", "abstract", "common", "prelude",
    # Shared Families
    "romance", "germanic", "scandinavian", "semitic", "slavic", "uralic", "hindustani",
    # Specific Languages
    "afrikaans", "amharic", "arabic", "basque", "bulgarian", "catalan", 
    "chinese", "danish", "dutch", "english", "estonian", "finnish", "french", 
    "german", "greek", "hebrew", "hindi", "hungarian", "icelandic", 
    "indonesian", "italian", "japanese", "korean", "latin", "latvian", 
    "lithuanian", "maltese", "mongolian", "nepali", "norwegian", "persian", 
    "polish", "portuguese", "punjabi", "romanian", "russian", "sindhi", 
    "slovenian", "somali", "spanish", "swahili", "swedish", "thai", "turkish", 
    "urdu", "vietnamese", "xhosa", "yoruba", "zulu"
]

def run():
    print("🚀 Starting Smart Compilation Loop (v3 - Shared Paths)...")
    
    abs_rgl = os.path.abspath(RGL_DIR)
    paths = [os.path.join(abs_rgl, folder) for folder in RGL_FOLDERS]
    # Filter out paths that don't exist to prevent warnings
    paths = [p for p in paths if os.path.exists(p)]
    path_str = ":".join(paths)

    attempt = 1
    
    while True:
        active_files = sorted(glob.glob(os.path.join(GF_DIR, "Wiki*.gf")))
        active_files = [f for f in active_files if not f.endswith(".SKIP")]
        
        if not active_files:
            print("❌ All languages disabled. Aborting.")
            break

        count = len(active_files)
        print(f"\n🔨 Attempt #{attempt}: Compiling {count} languages...")

        file_names = [os.path.basename(f) for f in active_files]
        cmd = ["gf", "-make", "-name=Wiki", "-path", path_str] + file_names

        try:
            result = subprocess.run(
                cmd, 
                cwd=GF_DIR, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                print(result.stdout)
                print("\n✅ SUCCESS: Wiki.pgf compiled successfully!")
                break
            
            output = result.stderr + result.stdout
            print(f"❌ Compilation Failed.")
            
            # --- STRATEGY 1: Explicit File Error (WikiCat.gf:10: ...) ---
            match = re.search(r"(Wiki[A-Z][a-z]{2})\.gf:\d+", output)
            
            # --- STRATEGY 2: Generic "File not found" inference ---
            if not match:
                # If we see "CatRomance.gf does not exist", we can't blame one file.
                # But if we see "SymbolicAra.gf does not exist", we know it's Arabic.
                dep_match = re.search(r"File (.*?) does not exist", output)
                if dep_match:
                    missing_file = dep_match.group(1) 
                    print(f"   ⚠️ Missing dependency: {missing_file}")
                    
                    # Try to guess language from missing file (SymbolicAra -> Ara)
                    code_match = re.search(r"([A-Z][a-z]{2})\.gf", missing_file)
                    if code_match:
                        lang_code = code_match.group(1) # Ara
                        suspect = f"Wiki{lang_code}.gf"
                        if suspect in file_names:
                            print(f"   (Inferred blame on {suspect})")
                            match = re.search(r"Wiki", "Wiki") # Fake match
                            bad_file_name = suspect

            if match:
                if 'bad_file_name' not in locals():
                    bad_file_name = match.group(1) + ".gf"
                
                full_path = os.path.join(GF_DIR, bad_file_name)
                print(f"   ✂️  Disabling {bad_file_name}...")
                
                if os.path.exists(full_path):
                    os.rename(full_path, full_path + ".SKIP")
                else:
                    print("   ⚠️ File not found? Aborting.")
                    break
            else:
                print("   ⚠️ Critical Error: Could not identify broken language.")
                print("   (It might be a shared dependency like CatRomance.gf missing)")
                print("\n   --- TAIL OF LOG ---")
                print("\n".join(output.splitlines()[-15:]))
                break

        except Exception as e:
            print(f"❌ Script Error: {e}")
            break
        
        attempt += 1

if __name__ == "__main__":
    run()