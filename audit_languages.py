import os
import subprocess
import glob
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_DIR = "gf-rgl/src"

# Include ALL RGL folders to ensure we don't fail on missing shared paths
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

def run():
    print("🚀 Starting Comprehensive Language Audit...")
    
    # Setup Paths
    abs_rgl = os.path.abspath(RGL_DIR)
    paths = [os.path.join(abs_rgl, f) for f in RGL_FOLDERS]
    path_str = ":".join(paths)
    
    # Get files
    files = sorted(glob.glob(os.path.join(GF_DIR, "Wiki*.gf")))
    files = [f for f in files if "Wiki.gf" not in f and not f.endswith(".SKIP")]
    
    valid = []
    broken = []
    
    print(f"   Scanning {len(files)} languages. This may take a moment...\n")

    for i, file_path in enumerate(files):
        filename = os.path.basename(file_path)
        lang = filename.replace("Wiki", "").replace(".gf", "")
        
        # Print progress bar
        sys.stdout.write(f"\r   [{i+1}/{len(files)}] Checking {lang:<10}")
        sys.stdout.flush()
        
        # Test Compile JUST this language
        # We assume Wiki.gf (abstract) is present and correct.
        cmd = ["gf", "-make", "-path", path_str, filename]
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=GF_DIR, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                valid.append(filename)
            else:
                # Capture the first error line
                error_lines = result.stderr.strip().split("\n")
                if not error_lines: error_lines = result.stdout.strip().split("\n")
                
                reason = "Unknown Error"
                for line in error_lines:
                    if "does not exist" in line:
                        reason = line.strip()
                        break
                    if "constant not found" in line:
                        reason = line.strip()
                        break
                
                broken.append((filename, reason))
                
        except Exception as e:
            broken.append((filename, str(e)))

    print("\n" + "="*60)
    print("AUDIT RESULTS")
    print("="*60)
    
    print(f"\n✅ VALID LANGUAGES ({len(valid)}):")
    print(", ".join([f.replace("Wiki", "").replace(".gf", "") for f in valid]))
    
    print(f"\n❌ BROKEN LANGUAGES ({len(broken)}):")
    disable_script = []
    for fname, reason in broken:
        print(f"   • {fname:<15} -> {reason}")
        disable_script.append(f"mv gf/{fname} gf/{fname}.SKIP")

    # Generate Fix Script
    with open("disable_broken.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write("\n".join(disable_script))
    
    print("\n" + "="*60)
    print("👉 To fix everything at once, run:")
    print("   bash disable_broken.sh")
    print("   python3 sync_config_from_gf.py")

if __name__ == "__main__":
    run()