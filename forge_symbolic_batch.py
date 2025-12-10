import os
import glob
import re

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_SRC = "gf-rgl/src"

# MAPPING: Wiki Code (File Name) -> RGL Code (Module Name)
LANG_MAP = {
    "Afr": "Afr", "Amh": "Amh", "Ara": "Ara", "Bas": "Eus", "Bul": "Bul", "Cat": "Cat", 
    "Chi": "Chi", "Zho": "Chi", "Dan": "Dan", "Deu": "Ger", "Dut": "Dut", "Eng": "Eng", 
    "Est": "Est", "Fin": "Fin", "Fra": "Fre", "Fre": "Fre", "Ger": "Ger", "Gre": "Gre", 
    "Heb": "Heb", "Hin": "Hin", "Hun": "Hun", "Ice": "Ice", "Ind": "Ind", "Ita": "Ita", 
    "Jap": "Jpn", "Jpn": "Jpn", "Kor": "Kor", "Lat": "Lat", "Lav": "Lav", "Lit": "Lit", 
    "Mlt": "Mlt", "Mon": "Mon", "Nep": "Nep", "Nno": "Nno", "Nor": "Nor", "Pan": "Pnb", 
    "Pes": "Pes", "Pol": "Pol", "Por": "Por", "Rom": "Ron", "Rus": "Rus", "Slv": "Slo", 
    "Snd": "Snd", "Som": "Som", "Spa": "Spa", "Swa": "Swa", "Swe": "Swe", "Tha": "Tha", 
    "Tur": "Tur", "Urd": "Urd", "Vie": "Vie", "Xho": "Xho", "Yor": "Yor", "Zul": "Zul"
}

# Target languages for the Simple Proper Name fix (Germanic, Romance, etc.)
# We will run this on ALL languages for uniformity, except for the known failures (Ara, Kor)
TARGETS_TO_SKIP_NOW = ["Ara", "Amh", "Heb", "Kor"] # Known complex symbolic/grammar failures

def find_rgl_path(rgl_code):
    """Safely finds the RGL folder name regardless of its capitalization."""
    target_dir_prefix = rgl_code.lower()
    
    # Search within gf-rgl/src/ for a directory matching the target prefix
    for item in os.listdir(RGL_SRC):
        if item.lower().startswith(target_dir_prefix):
            return item # Returns the correct casing (e.g., 'english', 'afrikaans')
    return None

def forge_symbolic(wiki_code, rgl_code):
    filename = os.path.join(GF_DIR, f"Symbolic{wiki_code}.gf")
    
    # The proven fix: open the Noun module for NP construction logic.
    content = f"""
resource Symbolic{wiki_code} = open Syntax, Paradigms{rgl_code}, Noun{rgl_code} in {{
  oper
    -- Use the Proper Name structure to construct an NP from a String (s)
    symb : Str -> NP = \\s -> mkNP (mkPN s) ; 
}}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"   🔨 Forged Symbolic{wiki_code}.gf ({rgl_code} PN fix).")

def run():
    print("🚀 Starting Batch Symbolic Fix (V2 - RGL Path Check)...")
    
    # Clean up any residual .gfo files
    os.system(f"rm {GF_DIR}/*.gfo 2>/dev/null")

    # Get all Wiki files (excluding WikiI)
    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    wiki_files = [f for f in wiki_files if "WikiI.gf" not in os.path.basename(f)]

    for file_path in wiki_files:
        wiki_code = os.path.basename(file_path)[4:-3] 
        if wiki_code in TARGETS_TO_SKIP_NOW: continue
        
        rgl_code = LANG_MAP.get(wiki_code, wiki_code)
        
        # 1. Verify Noun module exists in the correct folder structure
        rgl_folder = find_rgl_path(rgl_code)
        
        if rgl_folder:
            noun_file_path = os.path.join(RGL_SRC, rgl_folder, f"Noun{rgl_code}.gf")
            if not os.path.exists(noun_file_path):
                print(f"   ⚠️ Skipping {wiki_code}: Noun{rgl_code}.gf not found at {noun_file_path}")
                continue
        else:
            print(f"   ⚠️ Skipping {wiki_code}: RGL folder '{rgl_code.lower()}' not found.")
            continue
            
        # 2. Apply the fix
        forge_symbolic(wiki_code, rgl_code)

    print("\n✅ Batch Forge Complete.")

if __name__ == "__main__":
    run()