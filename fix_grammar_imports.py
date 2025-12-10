import os
import glob
import re

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_BASE = "gf-rgl/src"

# ISO -> Folder Name
LANG_TO_RGL = {
    "Afr": "afrikaans", "Amh": "amharic", "Ara": "arabic", "Bas": "basque",
    "Bul": "bulgarian", "Cat": "catalan", "Chi": "chinese", "Dan": "danish",
    "Deu": "german", "Dut": "dutch", "Eng": "english", "Est": "estonian",
    "Fin": "finnish", "Fra": "french", "Ger": "german", "Gre": "greek",
    "Heb": "hebrew", "Hin": "hindi", "Hun": "hungarian", "Ice": "icelandic",
    "Ind": "indonesian", "Ita": "italian", "Jap": "japanese", "Jpn": "japanese",
    "Kor": "korean", "Lat": "latin", "Lav": "latvian", "Lit": "lithuanian",
    "Mlt": "maltese", "Mon": "mongolian", "Nep": "nepali", "Nno": "norwegian",
    "Nor": "norwegian", "Pan": "punjabi", "Pes": "persian", "Pol": "polish",
    "Por": "portuguese", "Rom": "romanian", "Rus": "russian", "Slv": "slovenian",
    "Snd": "sindhi", "Som": "somali", "Spa": "spanish", "Swa": "swahili",
    "Swe": "swedish", "Tha": "thai", "Tur": "turkish", "Urd": "urdu",
    "Vie": "vietnamese", "Xho": "xhosa", "Yor": "yoruba", "Zul": "zulu",
    "Zho": "chinese"
}

def resolve_path(rgl_folder, module_name):
    """
    Checks if a module exists in the RGL language folder OR the API folder.
    """
    # 1. Check Language Folder (e.g. src/afrikaans/DictAfr.gf)
    p1 = os.path.join(RGL_BASE, rgl_folder, f"{module_name}.gf")
    if os.path.exists(p1): return True
    
    # 2. Check API Folder (e.g. src/api/SyntaxAfr.gf)
    p2 = os.path.join(RGL_BASE, "api", f"{module_name}.gf")
    if os.path.exists(p2): return True

    return False

def fix_file(file_path):
    filename = os.path.basename(file_path)
    lang_code = filename[4:-3] # WikiEng -> Eng
    
    rgl_folder = LANG_TO_RGL.get(lang_code)
    if not rgl_folder: return

    # Check if RGL folder exists
    full_rgl_path = os.path.join(RGL_BASE, rgl_folder)
    if not os.path.exists(full_rgl_path): return

    print(f"🔧 Checking {filename}...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    modified = False

    for line in lines:
        if line.strip().startswith("open"):
            match = re.search(r"open\s+(.*?)\s+in", line)
            if match:
                content = match.group(1)
                modules_raw = content.split(",")
                valid_modules = []
                
                for m in modules_raw:
                    m = m.strip()
                    # Clean name: "(S=SymbolicEng)" -> "SymbolicEng"
                    clean_name = m.split("=")[-1].replace("(", "").replace(")", "").strip()
                    
                    # Only check language-specific modules
                    if clean_name.endswith(lang_code):
                        if resolve_path(rgl_folder, clean_name):
                            valid_modules.append(m)
                        else:
                            print(f"   - Removing missing import: {clean_name}")
                            modified = True
                    else:
                        valid_modules.append(m)
                
                if valid_modules:
                    new_line = f"open {', '.join(valid_modules)} in {{\n"
                    new_lines.append(new_line)
                else:
                    print(f"   ! Warning: All imports removed for {filename}. Keeping line to allow compile error.")
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if modified:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("   💾 Saved changes.")

def run():
    files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    for f in files:
        if "Wiki.gf" in f: continue
        fix_file(f)

if __name__ == "__main__":
    run()