import os
import json
import pgf
import sys

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
PGF_PATH = os.path.join("gf", "Wiki.pgf")
PROFILES_PATH = os.path.join("language_profiles", "profiles.json")

# Map your Schema concepts to GF Abstract Functions
# (Adjust these keys to match exactly what is defined in your .gf files)
CONCEPT_MAP = {
    "copula": ["lex_copula_V", "be_V", "is_V"],  # Will try these in order
}

# Map ISO codes (Architect) to Concrete Syntax names (GF)
# If your GF names follow "WikiEng", "WikiFra", this helper tries to guess them.
# Add manual exceptions here.
ISO_TO_GF_MANUAL = {
    "zho": "WikiChi",  # Example: ISO is zho, GF might use Chi/Zho
    "fas": "WikiPes",  # Persian often Pes in standard libraries
}

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_linearization(concrete, function_name):
    """
    Safely extract the string linearization of a single lexical function.
    """
    try:
        # We assume the function has no arguments (lexical item)
        # In PGF, we construct a tree of just that function
        expr = pgf.readExpr(function_name) 
        return concrete.linearize(expr)
    except Exception:
        return None

def find_copula(concrete):
    """
    Tries multiple function names to find the copula.
    """
    for fn in CONCEPT_MAP["copula"]:
        if concrete.hasFunctions(fn): # Hypothetical helper, or just try/except
            res = get_linearization(concrete, fn)
            if res:
                return res
    return None

# -----------------------------------------------------------------------------
# MAIN LOGIC
# -----------------------------------------------------------------------------
def run():
    print(f"🚀 Syncing Language Cards from GF: {PGF_PATH}")
    
    if not os.path.exists(PGF_PATH):
        print(f"❌ PGF file missing. Please build your grammar first.")
        sys.exit(1)

    grammar = pgf.readPGF(PGF_PATH)
    profiles = load_json(PROFILES_PATH)
    
    if not profiles:
        print("❌ No profiles found in language_profiles/profiles.json")
        sys.exit(1)

    updated_count = 0

    for iso_code, profile in profiles.items():
        # 1. Determine Target File Path
        family = profile.get("family", "analytic") # Default folder
        target_dir = os.path.join("data", family)
        target_file = os.path.join(target_dir, f"{iso_code}.json")
        
        # Ensure dir exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Load existing config or start fresh
        config = load_json(target_file)

        # 2. Find GF Concrete Grammar
        # Try "Wiki" + TitleCase(iso) or lookups
        gf_lang_name = ISO_TO_GF_MANUAL.get(iso_code)
        
        if not gf_lang_name:
            # Fallback heuristic: eng -> WikiEng, fra -> WikiFra
            # You might need to adjust logic based on your actual .gf names
            candidates = [
                f"Wiki{iso_code.capitalize()}", # WikiEng
                f"Wiki{iso_code.upper()}",      # WikiENG
                f"Food{iso_code.capitalize()}"  # If using Food grammar example
            ]
            for cand in candidates:
                if cand in grammar.languages:
                    gf_lang_name = cand
                    break
        
        if not gf_lang_name or gf_lang_name not in grammar.languages:
            print(f"⚠️  [{iso_code}] No matching GF concrete grammar found. Skipping GF sync.")
            # We still save the file if it didn't exist, to prevent 'File Not Found' errors
            if not os.path.exists(target_file):
                save_json(target_file, config)
            continue

        concrete = grammar.languages[gf_lang_name]
        print(f"   [{iso_code}] Found Grammar: {gf_lang_name}")

        # 3. Extract Data from GF
        
        # --- COPULA ---
        # Note: In RGL, "be_V" often linearizes to infinite form. 
        # For simple engines, we might want the present tense string.
        # This simple extractor gets the default linearization.
        copula_text = find_copula(concrete)
        if copula_text:
            config["copula"] = {"lemma": copula_text, "source": "gf_extraction"}
            print(f"      - Copula: {copula_text}")
        
        # --- ARTICLES (Advanced) ---
        # This is harder to extract generically without knowing the Grammar's inflection tables.
        # But we can try to linearize specific trees if your grammar defines them, 
        # e.g., "mkNP (DetSg Masc) ..." 
        # For now, we leave articles to be manually filled or populated by populate_data.py
        # to avoid overwriting them with bad data.

        # 4. Save
        save_json(target_file, config)
        updated_count += 1

    print(f"\n✅ Sync Complete. Updated {updated_count} language cards.")

if __name__ == "__main__":
    run()