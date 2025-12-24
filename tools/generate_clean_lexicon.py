import json
from pathlib import Path

def clean_token(text):
    """
    Escape strings for GF. 
    1. Escape backslashes.
    2. Escape double quotes.
    """
    if not text: return ""
    return text.replace('\\', '\\\\').replace('"', '\\"')

def generate_clean_lexicon(lang_code):
    # Path to your harvested data
    json_path = Path(f"data/lexicon/{lang_code}/wide.json")
    if not json_path.exists():
        print(f"❌ JSON not found: {json_path}")
        return

    print(f"⚙️  Reading {json_path}...")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. Start Abstract Interface
    # We use 'Cat' module from RGL to get standard categories (N, PN, etc.)
    abs_lines = [
        f"abstract WikiLexicon = Cat ** {{",
        f"  fun"
    ]
    
    # 2. Start Concrete Implementation
    # We open 'Paradigms...' to get mkN, mkPN
    cnc_lines = [
        f"concrete WikiLexicon{lang_code.capitalize()} of WikiLexicon = Cat{lang_code.capitalize()} ** open Paradigms{lang_code.capitalize()} in {{",
        f"  lin"
    ]

    count = 0
    seen_funcs = set()
    skipped = 0

    for key, entry in data.items():
        # Handle list vs dict format
        if isinstance(entry, list): entry = entry[0]
        
        func = entry.get('gf_fun')
        lemma = entry.get('lemma')
        
        if not func or not lemma: continue
        if func in seen_funcs: continue
        
        # SAFETY FILTER: Only allow alphanumeric identifiers (plus underscores)
        # Some WordNet keys have weird chars like '3-D_place_N' which GF hates if not quoted.
        if not func.replace("_", "").isalnum():
            skipped += 1
            continue

        seen_funcs.add(func)

        # Only export Nouns (N, PN) and Adjectives (A) to keep it stable
        if func.endswith("_N") or func.endswith("_PN") or func.endswith("_A"):
            
            # Determine Category
            if func.endswith("_N"): cat = "N"
            elif func.endswith("_PN"): cat = "PN"
            elif func.endswith("_A"): cat = "A"
            else: continue

            # Append Abstract
            abs_lines.append(f"    {func} : {cat} ;")

            # Append Concrete
            # We use the 'clean_token' to prevent syntax errors on words like "d'Ivoire"
            if cat == "N":
                cnc_lines.append(f"    {func} = mkN \"{clean_token(lemma)}\" ;")
            elif cat == "PN":
                cnc_lines.append(f"    {func} = mkPN \"{clean_token(lemma)}\" ;")
            elif cat == "A":
                cnc_lines.append(f"    {func} = mkA \"{clean_token(lemma)}\" ;")
            
            count += 1

    abs_lines.append("}")
    cnc_lines.append("}")

    # Write Files to 'gf/' directory
    with open("gf/WikiLexicon.gf", "w", encoding='utf-8') as f:
        f.write("\n".join(abs_lines))
        
    with open(f"gf/WikiLexicon{lang_code.capitalize()}.gf", "w", encoding='utf-8') as f:
        f.write("\n".join(cnc_lines))

    print(f"✅ Generated 'gf/WikiLexicon.gf' with {count} entries (Skipped {skipped} complex keys).")

if __name__ == "__main__":
    generate_clean_lexicon("eng")