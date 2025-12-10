import json
import os

# --- Configuration ---
MAP_FILE = 'rgl_map.json'
PATHS_FILE = 'rgl_paths.json'

ABSTRACT_WIKI = """
abstract Wiki = {
  flags startcat = Phr ;
  cat
    Phr ; NP ; CN ; Adv ;
  fun
    -- Structural
    SimpNP : CN -> NP ;
    
    -- Dictionary
    John : NP ;
    Here : Adv ;
    apple_N : CN ;
}
"""

def load_json(filename):
    if not os.path.exists(filename):
        print(f"Error: {filename} not found.")
        return {}
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_grammars():
    data_map = load_json(MAP_FILE)
    data_paths = load_json(PATHS_FILE)
    
    module_map = data_map.get('module_map', {})
    
    # We still use the skip list for languages known to be truly broken/incomplete
    skip_list = set(data_map.get('skip_list', []))

    print("Generating Abstract Wiki.gf...")
    with open("Wiki.gf", "w", encoding="utf-8") as f:
        f.write(ABSTRACT_WIKI)

    generated_langs = []
    
    for wiki_code, rgl_code in module_map.items():
        if wiki_code in skip_list:
            print(f"Skipping {wiki_code} (in skip_list)")
            continue

        cat_key = f"Cat{rgl_code}"
        if cat_key not in data_paths:
            print(f"Warning: Module {cat_key} not found. Skipping {wiki_code}.")
            continue

        wiki_mod = f"Wiki{wiki_code}"
        
        # Imports: CatX, NounX, ParadigmsX
        imports = [
            f"Cat{rgl_code}",
            f"Noun{rgl_code}",
            f"Paradigms{rgl_code}"
        ]

        # THE FIX:
        # mkNP and mkCN are standard GF Syntax constructors (available via SyntaxX).
        # mkPN, mkAdv, mkN are Lexical constructors (available via ParadigmsX).
        content = f"""
concrete {wiki_mod} of Wiki = {", ".join(imports[:-1])} ** open Syntax{rgl_code}, (P = {imports[-1]}) in {{

  lin
    -- Structural
    SimpNP cn = mkNP cn ;

    -- Lexicon
    -- We use standard Syntax constructors (mkNP, mkCN) directly
    -- We use Paradigms constructors (P.mkPN, P.mkN, P.mkAdv) via P
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}}
"""
        with open(f"{wiki_mod}.gf", "w", encoding="utf-8") as f:
            f.write(content.strip())
        
        generated_langs.append(wiki_code)

    print(f"\nSuccessfully generated {len(generated_langs)} language files.")

if __name__ == "__main__":
    generate_grammars()