import os
import glob
import re
import subprocess
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
# Keep this relative for the Python checks to work
RGL_DIR = "gf-rgl/src"

LANG_TO_RGL = {
    "Afr": "afrikaans", "Amh": "amharic",   "Ara": "arabic",    "Bas": "basque",
    "Bul": "bulgarian", "Cat": "catalan",   "Chi": "chinese",   "Zho": "chinese",
    "Dan": "danish",    "Deu": "german",    "Ger": "german",    "Dut": "dutch",
    "Eng": "english",   "Est": "estonian",  "Fin": "finnish",   "Fra": "french",
    "Fre": "french",    "Gre": "greek",     "Heb": "hebrew",    "Hin": "hindi",
    "Hun": "hungarian", "Ice": "icelandic", "Ind": "indonesian","Ita": "italian",
    "Jap": "japanese",  "Jpn": "japanese",  "Kor": "korean",    "Lat": "latin",
    "Lav": "latvian",   "Lit": "lithuanian","Mlt": "maltese",   "Mon": "mongolian",
    "Nep": "nepali",    "Nno": "norwegian", "Nor": "norwegian", "Pan": "punjabi",
    "Pes": "persian",   "Pol": "polish",    "Por": "portuguese","Rom": "romanian",
    "Rus": "russian",   "Slv": "slovenian", "Snd": "sindhi",    "Som": "somali",
    "Spa": "spanish",   "Swa": "swahili",   "Swe": "swedish",   "Tha": "thai",
    "Tur": "turkish",   "Urd": "urdu",      "Vie": "vietnamese","Xho": "xhosa",
    "Yor": "yoruba",    "Zul": "zulu"
}

CORE_PATHS = ["api", "abstract", "common", "prelude"]

def get_imports(gf_file):
    imports = set()
    try:
        with open(gf_file, "r", encoding="utf-8") as f:
            content = f.read()
            matches = re.findall(r'open\s+(.*?)\s+in', content, re.DOTALL)
            for match in matches:
                modules = [m.strip().split('(')[0] for m in match.split(',')]
                imports.update(modules)
    except Exception as e:
        print(f"   [Error reading {gf_file}: {e}]")
    return imports

def resolve_module(module_name, lang_folder_name):
    p1 = os.path.join(RGL_DIR, lang_folder_name, f"{module_name}.gf")
    if os.path.exists(p1): return True
    p2 = os.path.join(RGL_DIR, "api", f"{module_name}.gf")
    if os.path.exists(p2): return True
    return False

def run():
    print("🚀 Starting Smart Dependency Check (Absolute Paths)...")
    
    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    valid_langs = []
    
    # Reset .SKIP files
    for skip_file in glob.glob(os.path.join(GF_DIR, "*.SKIP")):
        restored = skip_file.replace(".SKIP", "")
        os.rename(skip_file, restored)
        wiki_files.append(restored)

    include_paths = set()
    for p in CORE_PATHS:
        include_paths.add(os.path.join(RGL_DIR, p))

    print(f"   (Checking {len(wiki_files)} languages...)")

    for file_path in wiki_files:
        filename = os.path.basename(file_path)
        if filename == "Wiki.gf": continue 
        if filename.endswith(".SKIP"): continue

        lang_code = filename[4:-3] 
        rgl_folder = LANG_TO_RGL.get(lang_code)

        if not rgl_folder:
            print(f"   ❌ {filename}: No RGL mapping -> Disabling.")
            os.rename(file_path, file_path + ".SKIP")
            continue

        rgl_path = os.path.join(RGL_DIR, rgl_folder)
        
        if not os.path.exists(rgl_path):
            print(f"   ❌ {filename}: RGL folder missing -> Disabling.")
            os.rename(file_path, file_path + ".SKIP")
            continue

        required_modules = get_imports(file_path)
        missing_dep = False
        
        for mod in required_modules:
            if mod.endswith(lang_code): 
                if not resolve_module(mod, rgl_folder):
                    print(f"   ❌ {filename}: Missing dependency '{mod}' -> Disabling.")
                    missing_dep = True
                    break
        
        if missing_dep:
            os.rename(file_path, file_path + ".SKIP")
            continue

        valid_langs.append(filename)
        include_paths.add(rgl_path)

    if not valid_langs:
        print("❌ No valid languages found! Check your paths.")
        sys.exit(1)

    print(f"\n🔨 Compiling {len(valid_langs)} languages...")
    
    # --- THE FIX IS HERE ---
    # Convert all include_paths to ABSOLUTE paths so GF finds them from anywhere
    abs_include_paths = [os.path.abspath(p) for p in include_paths]
    path_str = ":".join(abs_include_paths)
    
    cmd = ["gf", "-make", "-name=Wiki", "-path", path_str] + valid_langs
    
    try:
        subprocess.run(cmd, cwd=GF_DIR, check=True)
        print("\n🎉 Build SUCCESS! Wiki.pgf is ready.")
    except subprocess.CalledProcessError:
        print("\n❌ Build FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run()