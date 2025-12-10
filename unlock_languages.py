import os
import glob
import re
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
RGL_DIR = "gf-rgl/src"

# ISO Map: Your Wiki Code -> The RGL Code (e.g. Bas -> Eus)
# This maps languages where your filename differs from RGL's internal naming.
CODE_SWAP = {
    "Bas": "Eus", # Basque
    "Chi": "Chi", "Zho": "Chi", # Chinese
    "Dan": "Dan", 
    "Dut": "Dut",
    "Eng": "Eng",
    "Est": "Est",
    "Fin": "Fin",
    "Fra": "Fre", "Fre": "Fre", # French
    "Ger": "Ger", "Deu": "Ger", # German
    "Gre": "Gre", "Ell": "Gre", # Greek
    "Heb": "Heb",
    "Hin": "Hin",
    "Hun": "Hun",
    "Ice": "Ice", "Isl": "Ice", # Icelandic
    "Ind": "Ind",
    "Ita": "Ita",
    "Jap": "Jpn", "Jpn": "Jpn", # Japanese
    "Kor": "Kor",
    "Lat": "Lat",
    "Lav": "Lav",
    "Lit": "Lit",
    "Mlt": "Mlt",
    "Mon": "Mon",
    "Nep": "Nep",
    "Nno": "Nno", "Nob": "Nor", "Nor": "Nor", # Norwegian variations
    "Pan": "Pnb", # Punjabi (often Pnb in RGL)
    "Pes": "Pes", "Fas": "Pes", # Persian
    "Pol": "Pol",
    "Por": "Por",
    "Rom": "Ron", "Ron": "Ron", # Romanian
    "Rus": "Rus",
    "Slv": "Slo", "Slo": "Slo", # Slovenian
    "Snd": "Snd",
    "Som": "Som",
    "Spa": "Spa",
    "Swa": "Swa",
    "Swe": "Swe",
    "Tha": "Tha",
    "Tur": "Tur",
    "Urd": "Urd",
    "Vie": "Vie",
    "Xho": "Xho",
    "Yor": "Yor",
    "Zul": "Zul"
}

def resolve_module(module_name):
    """
    Checks if a module exists in the RGL (Language folder or API).
    Returns the Correct Name if found, or None.
    """
    # 1. Check exact name in API (e.g. SyntaxEng.gf)
    if os.path.exists(os.path.join(RGL_DIR, "api", f"{module_name}.gf")):
        return module_name
    
    # 2. Check exact name in Language Folder
    # We don't know the folder name easily here without the big map, 
    # but we can scan or assume standard paths. 
    # For now, relying on API check is robust for Syntax/Symbolic.
    
    return None

def run():
    print("🚀 Unlocking Languages (Restoring & Fixing Imports)...")

    # 1. Restore .SKIP files
    skip_files = glob.glob(os.path.join(GF_DIR, "*.SKIP"))
    for sf in skip_files:
        original = sf.replace(".SKIP", "")
        os.rename(sf, original)
        print(f"   Restored: {os.path.basename(original)}")

    # 2. Process ALL Wiki*.gf files
    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    
    for file_path in wiki_files:
        filename = os.path.basename(file_path)
        if filename == "Wiki.gf": continue

        # Your Code: WikiBas -> Bas
        my_code = filename[4:-3]
        # Target RGL Code: Bas -> Eus
        rgl_code = CODE_SWAP.get(my_code, my_code)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find the "open ... in" block
        # Matches: "open SyntaxBas, SymbolicBas in"
        pattern = r"(open\s+)(.*?)(\s+in)"
        
        def fixer(match):
            prefix = match.group(1)
            modules_str = match.group(2)
            suffix = match.group(3)
            
            new_modules = []
            
            # Split "SyntaxBas, (S=SymbolicBas)"
            # Rough split by comma
            raw_mods = modules_str.split(",")
            
            for m in raw_mods:
                m = m.strip()
                clean_m = m.split("=")[-1].replace("(","").replace(")","").strip()
                
                # Identify the suffix (e.g. "Bas" in "SyntaxBas")
                # We want to replace "Bas" with "Eus" if needed, 
                # OR drop it if the file doesn't exist.
                
                # Construct Candidate 1: As Is
                if resolve_module(clean_m):
                    new_modules.append(m)
                    continue

                # Construct Candidate 2: Swapped Code (SyntaxBas -> SyntaxEus)
                if my_code in clean_m:
                    swapped_name = clean_m.replace(my_code, rgl_code)
                    if resolve_module(swapped_name):
                        # It exists! Use the swapped name.
                        # We might need to alias it: "(SyntaxBas=SyntaxEus)" 
                        # but usually just using SyntaxEus is fine for Abstract Wiki.
                        new_modules.append(swapped_name)
                        continue

                # If we get here, neither SyntaxBas nor SyntaxEus exists.
                # DROP IT.
                print(f"      [{filename}] Dropping broken import: {clean_m}")

            if not new_modules:
                # If we killed everything, the file is dead.
                # Keep Syntax at least to force a compile error? 
                # Or just leave empty (will fail parse).
                return f"{prefix} -- NO VALID IMPORTS -- {suffix}"
                
            return f"{prefix}{', '.join(new_modules)}{suffix}"

        # Apply Fix
        new_content = re.sub(pattern, fixer, content, flags=re.DOTALL)
        
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"   ✅ Fixed imports in {filename}")

    print("\n🏁 Unlock Complete. Ready to Compile.")

if __name__ == "__main__":
    run()