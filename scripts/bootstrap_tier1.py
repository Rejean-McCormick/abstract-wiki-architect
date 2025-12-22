import json
import os
import glob
import sys

# The "Proper" Source of Truth
MATRIX_PATH = "data/indices/everything_matrix.json"
RGL_SRC_PATH = "gf-rgl/src"
APP_GF_PATH = "gf"

def detect_rgl_suffix(folder_path):
    """
    Scans a folder like 'gf-rgl/src/german' to find 'GrammarGer.gf'.
    Returns the suffix 'Ger'.
    """
    if not os.path.exists(folder_path):
        return None
    
    # Look for Grammar*.gf to identify the 3-letter RGL code
    # e.g., GrammarGer.gf -> Suffix is Ger
    pattern = os.path.join(folder_path, "Grammar*.gf")
    files = glob.glob(pattern)
    
    for f in files:
        filename = os.path.basename(f)
        # Extract X from GrammarX.gf
        if filename.startswith("Grammar") and filename.endswith(".gf"):
            suffix = filename[7:-3] # Strip 'Grammar' and '.gf'
            return suffix
    return None

def main():
    print(f"📂 Loading Registry: {MATRIX_PATH}")
    
    if not os.path.exists(MATRIX_PATH):
        print("❌ Matrix not found. Run 'python manage.py build' first to generate indices.")
        sys.exit(1)

    with open(MATRIX_PATH, "r", encoding="utf-8") as f:
        matrix = json.load(f)

    languages = matrix.get("languages", {})
    print(f"🔍 Found {len(languages)} languages in Matrix. filtering for Tier 1...")

    count = 0
    for iso_code, data in languages.items():
        # 1. Filter: We only bootstrap Tier 1 (RGL) languages
        meta = data.get("meta", {})
        if meta.get("tier") != 1:
            continue

        folder_name = meta.get("folder") # e.g. "german"
        if not folder_name:
            print(f"⚠️  Skipping {iso_code}: No folder defined in matrix.")
            continue

        # 2. Resolution: Map ISO (deu) -> Folder (german) -> Suffix (Ger)
        rgl_folder_path = os.path.join(RGL_SRC_PATH, folder_name)
        suffix = detect_rgl_suffix(rgl_folder_path)

        if not suffix:
            print(f"⚠️  Skipping {iso_code}: Could not detect RGL suffix in {rgl_folder_path}")
            continue

        # 3. Action: Create the Bridge (SyntaxGer.gf)
        bridge_file = os.path.join(rgl_folder_path, f"Syntax{suffix}.gf")
        if not os.path.exists(bridge_file):
            with open(bridge_file, "w") as f:
                f.write(f"instance Syntax{suffix} of Syntax = Grammar{suffix} ** {{ flags coding=utf8 ; }};\n")
            print(f"   ✅ [RGL] Created Bridge: Syntax{suffix}.gf ({iso_code})")
        
        # 4. Action: Create the Application Grammar (WikiDeu.gf)
        # Note: We capitalize the ISO code for the filename (WikiDeu) but link to RGL suffix (Ger)
        app_file = os.path.join(APP_GF_PATH, f"Wiki{iso_code.capitalize()}.gf")
        
        content = (
            f"concrete Wiki{iso_code.capitalize()} of AbstractWiki = WikiI with (Syntax = Syntax{suffix}) ** "
            f"open Syntax{suffix}, Paradigms{suffix} in {{ flags coding = utf8 ; }};\n"
        )
        
        # Always write/overwrite to ensure correctness
        with open(app_file, "w") as f:
            f.write(content)
        
        count += 1

    print(f"\n🚀 Bootstrapped {count} Tier 1 languages based on the Everything Matrix.")

if __name__ == "__main__":
    main()