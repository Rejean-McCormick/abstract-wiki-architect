import os
import glob
import re
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
# Based on your ls -F output, gf-rgl is in the project root
RGL_BASE = "gf-rgl/src"

# ISO 3-letter code -> RGL Directory Name
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

def get_imports(gf_file):
    """Parses a GF file to find modules opened in the main body."""
    imports = set()
    try:
        with open(gf_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Regex captures "open (Module1), Module2, (Module3) in"
            matches = re.findall(r'open\s+(.*?)\s+in', content, re.DOTALL)
            for match in matches:
                # Split by comma, strip parens and whitespace
                modules = [m.strip().replace('(', '').replace(')', '') for m in match.split(',')]
                imports.update(modules)
    except Exception as e:
        print(f"   [Error reading {gf_file}: {e}]")
    return imports

def run():
    print(f"🔍 Scanning for RGL dependencies in: {GF_DIR}")
    print(f"📂 Checking against RGL source:     {RGL_BASE}\n")
    
    wiki_files = sorted(glob.glob(os.path.join(GF_DIR, "Wiki*.gf")))
    
    missing_count = 0
    clean_langs = 0

    for file_path in wiki_files:
        filename = os.path.basename(file_path)
        if filename == "Wiki.gf": continue
        
        # Heuristic: WikiAfr.gf -> Afr
        lang_code = filename[4:-3]
        rgl_folder = LANG_TO_RGL.get(lang_code)

        # 1. Check if we know where this language lives in RGL
        if not rgl_folder:
            print(f"⚠️  {filename}: Unknown RGL mapping for code '{lang_code}'")
            missing_count += 1
            continue
            
        rgl_path = os.path.join(RGL_BASE, rgl_folder)
        if not os.path.exists(rgl_path):
            print(f"❌ {filename}: RGL folder missing -> {rgl_path}")
            missing_count += 1
            continue

        # 2. Check specific file dependencies
        dependencies = get_imports(file_path)
        file_errors = []

        for mod in dependencies:
            # We only check dependencies that end in the language code (e.g. SymbolicAfr)
            # Generic ones like 'Syntax' or 'Prelude' are assumed safe in core RGL.
            if mod.endswith(lang_code):
                expected_file = os.path.join(rgl_path, f"{mod}.gf")
                if not os.path.exists(expected_file):
                    file_errors.append(f"{mod}.gf")

        if file_errors:
            print(f"❌ {filename}: Missing dependencies in {rgl_folder}/")
            for err in file_errors:
                print(f"      - {err}")
            missing_count += 1
        else:
            print(f"✅ {filename}: All files found.")
            clean_langs += 1

    print("-" * 60)
    print(f"Summary: {clean_langs} valid languages, {missing_count} broken.")

if __name__ == "__main__":
    run()