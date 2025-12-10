import json
import os

# --- Configuration ---
MAP_FILE = 'rgl_map.json'
PATHS_FILE = 'rgl_paths.json'

# Robust Abstract Grammar (Wiki.gf)
ABSTRACT_WIKI = """
abstract Wiki = {
  flags startcat = Phr ;
  cat
    Phr ; NP ; CN ; Adv ;
  fun
    -- Symbolic / Structure
    SimpNP : CN -> NP ;
    
    -- Dictionary / Lexicon
    John : NP ;
    Here : Adv ;
    apple_N : CN ;
}
"""

# Robust Abstract Dictionary (Dict.gf)
ABSTRACT_DICT = """
abstract Dict = Wiki ** {
  -- This creates a separation for purely lexical entries if needed
  -- For this build, we map entries directly in the Concrete Wiki for simplicity
}
"""

def load_json(filename):
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_grammars():
    # 1. Load Data
    data_map = load_json(MAP_FILE)
    data_paths = load_json(PATHS_FILE)
    
    module_map = data_map.get('module_map', {})
    skip_list = set(data_map.get('skip_list', []))

    # 2. Generate Abstracts
    print("Generating Abstract Wiki.gf...")
    with open("Wiki.gf", "w", encoding="utf-8") as f:
        f.write(ABSTRACT_WIKI)

    # 3. Iterate Languages
    generated_langs = []
    
    for wiki_code, rgl_code in module_map.items():
        # Check Skip List
        if wiki_code in skip_list:
            print(f"Skipping {wiki_code} (in skip_list)")
            continue

        # Validate existence via rgl_paths.json
        # We check if the specific Cat and Noun modules exist for this RGL code
        cat_key = f"Cat{rgl_code}"
        noun_key = f"Noun{rgl_code}"
        
        if cat_key not in data_paths:
            print(f"Warning: Module {cat_key} not found in paths. Skipping {wiki_code}.")
            continue

        # Define Module Names
        wiki_mod = f"Wiki{wiki_code}"
        
        # Determine Imports
        # We need Cat, Noun, and Paradigms. 
        # rgl_paths confirms Cat/Noun exist. Paradigms usually matches RGL code.
        imports = [
            f"Cat{rgl_code}",
            f"Noun{rgl_code}",
            f"Paradigms{rgl_code}"
        ]

        # 4. Generate Concrete File
        # We use a combined structure (Lexicon + Syntax) for the immediate build to minimize dependency issues.
        # Note the specific strict syntax injection: mkNP (mkPN "...")
        
        content = f"""
concrete {wiki_mod} of Wiki = {", ".join(imports[:-1])} ** open Syntax{rgl_code}, (P = {imports[-1]}) in {{

  lin
    -- Structural
    SimpNP cn = mkNP cn ;

    -- Lexicon (Safe Injection)
    John = P.mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = P.mkCN (P.mkN "apple") ;
}}
"""
        with open(f"{wiki_mod}.gf", "w", encoding="utf-8") as f:
            f.write(content.strip())
        
        generated_langs.append(wiki_code)
        print(f"Generated {wiki_mod}.gf (mapped to {rgl_code})")

    print(f"\nSuccessfully generated {len(generated_langs)} language files.")
    return generated_langs

if __name__ == "__main__":
    generate_grammars()