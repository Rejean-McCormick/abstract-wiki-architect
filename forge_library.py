import os
import glob
import re

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
GF_DIR = "gf"
TEMPLATE_LANG = "Eng" # We use English as the source of truth

# If a language lacks a specific Paradigm (like ParadigmsAfr), 
# we fallback to this generic string-based construction to force compilation.
GENERIC_paradigm = """
  oper
    mkN = overload {
      mkN : Str -> N = \\s -> lin N {s = s} ;
    } ;
    mkA = overload {
      mkA : Str -> A = \\s -> lin A {s = s} ;
    } ;
    mkV = overload {
      mkV : Str -> V = \\s -> lin V {s = s} ;
    } ;
    mkAdv : Str -> Adv = \\s -> lin Adv {s = s} ;
"""

def get_required_lexicon():
    """Reads WikiEng.gf to find all required lex_ functions."""
    lex_keys = []
    try:
        with open(os.path.join(GF_DIR, f"Wiki{TEMPLATE_LANG}.gf"), "r", encoding="utf-8") as f:
            for line in f:
                # Look for lines like: lin animal_Entity = lex_animal_N ;
                match = re.search(r"lin \w+ = (lex_\w+)", line)
                if match:
                    lex_keys.append(match.group(1))
    except FileNotFoundError:
        print(f"❌ Critical: Wiki{TEMPLATE_LANG}.gf not found. Cannot determine lexicon.")
    return sorted(list(set(lex_keys)))

def forge_symbolic(lang_code):
    """Creates a minimal Symbolic file if missing."""
    filename = os.path.join(GF_DIR, f"Symbolic{lang_code}.gf")
    if os.path.exists(filename): return

    print(f"   🔨 Forging Symbolic{lang_code}.gf...")
    content = f"""
resource Symbolic{lang_code} = open Prelude, Syntax{lang_code} in {{
  oper
    symb : Str -> NP = \\s -> 
      lin NP {{ s = \\c -> s ; a = agrP3 Sg }} ; -- Minimal stub
}}
"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def forge_dictionary(lang_code, required_keys):
    """Creates or updates Dict file with missing keys."""
    filename = os.path.join(GF_DIR, f"Dict{lang_code}.gf")
    
    existing_content = ""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            existing_content = f.read()

    missing_keys = [k for k in required_keys if k not in existing_content]
    
    if not missing_keys and os.path.exists(filename):
        return # Nothing to do

    print(f"   🔨 Forging Dict{lang_code}.gf ({len(missing_keys)} new entries)...")

    # If file is new, write header
    if not os.path.exists(filename):
        # We try to open standard Paradigms. If it fails compilation later, 
        # the user might need to use the generic fallback, but let's try standard first.
        header = f"""
resource Dict{lang_code} = open Cat{lang_code}, Paradigms{lang_code}, Syntax{lang_code} in {{
  operc
    -- This file is auto-generated stub. Run AI seeder to translate.
"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(header)
    
    # Append missing keys
    with open(filename, "a", encoding="utf-8") as f:
        for key in missing_keys:
            # key is like lex_animal_N or lex_blue_A
            word = key.replace("lex_", "").split("_")[0] # "animal"
            
            # Simple heuristic for type
            if key.endswith("_N"):
                line = f"    {key} = mkN \"{word}\" ;\n"
            elif key.endswith("_A"):
                line = f"    {key} = mkA \"{word}\" ;\n"
            elif key.endswith("_V"):
                line = f"    {key} = mkV \"{word}\" ;\n"
            elif key.endswith("_Adv"):
                line = f"    {key} = mkAdv \"{word}\" ;\n"
            else:
                line = f"    {key} = mkN \"{word}\" ; -- Guessing N\n"
            
            f.write(line)
        
        if "}" not in existing_content:
             f.write("}\n")

def run():
    print("🚀 Starting Library Forge...")
    
    # 1. Get List of "Wiki*.gf" files
    wiki_files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    # Also include .SKIP files because we want to fix them!
    wiki_files += glob.glob(os.path.join(GF_DIR, "Wiki*.gf.SKIP"))
    
    required_lexicon = get_required_lexicon()
    print(f"   ℹ️  Found {len(required_lexicon)} lexicon items required by Abstract.")

    for file_path in wiki_files:
        filename = os.path.basename(file_path)
        if filename == "Wiki.gf": continue
        
        # Extract Lang Code (WikiChi.gf.SKIP -> Chi)
        clean_name = filename.replace(".SKIP", "")
        lang_code = clean_name[4:-3] 
        
        # 2. Fix Symbolic
        forge_symbolic(lang_code)
        
        # 3. Fix Dictionary
        forge_dictionary(lang_code, required_lexicon)
        
        # 4. Restore file if it was disabled
        if file_path.endswith(".SKIP"):
            new_path = file_path.replace(".SKIP", "")
            os.rename(file_path, new_path)
            print(f"   ✨ Restored {clean_name}")

    print("\n✅ Forge Complete. Files are ready for compilation.")

if __name__ == "__main__":
    run()