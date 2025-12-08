import os
import shutil

# ===========================================================================
# LANGUAGE FACTORY CONFIGURATION (TIER 3)
# ===========================================================================
# This dictionary defines the "DNA" for languages that do not exist in the
# official Resource Grammar Library.
#
# Schema: "iso_code": { "name": "CamelCaseName", "order": "SVO"|"SOV"|"VSO" }
#
# NOTE: This list acts as the seed. In the future, we can expand this to
# 300+ entries or load it from an external JSON/CSV.
# ===========================================================================

FACTORY_CONFIGS = {
    # --- AFRICA (Bantu / Niger-Congo / Afroasiatic) ---
    "zul": {"name": "Zulu",        "order": "SVO"},
    "xho": {"name": "Xhosa",       "order": "SVO"},
    "yor": {"name": "Yoruba",      "order": "SVO"},
    "ibo": {"name": "Igbo",        "order": "SVO"},
    "hau": {"name": "Hausa",       "order": "SVO"},
    "swa": {"name": "Swahili",     "order": "SVO"}, # Fallback if RGL fails
    "wol": {"name": "Wolof",       "order": "SVO"},
    "kin": {"name": "Kinyarwanda", "order": "SVO"},
    "lug": {"name": "Ganda",       "order": "SVO"},
    "lin": {"name": "Lingala",     "order": "SVO"},
    "som": {"name": "Somali",      "order": "SOV"}, # Often SOV

    # --- ASIA (Austronesian / Dravidian / Turkic) ---
    "kor": {"name": "Korean",      "order": "SOV"},
    "ind": {"name": "Indonesian",  "order": "SVO"},
    "msa": {"name": "Malay",       "order": "SVO"},
    "tgl": {"name": "Tagalog",     "order": "VSO"}, # Verb-Initial
    "vie": {"name": "Vietnamese",  "order": "SVO"},
    "jav": {"name": "Javanese",    "order": "SVO"},
    "tam": {"name": "Tamil",       "order": "SOV"},
    "tel": {"name": "Telugu",      "order": "SOV"},
    "ben": {"name": "Bengali",     "order": "SOV"},
    "uzb": {"name": "Uzbek",       "order": "SOV"},
    "kaz": {"name": "Kazakh",      "order": "SOV"},

    # --- AMERICAS (Indigenous) ---
    "que": {"name": "Quechua",     "order": "SOV"},
    "aym": {"name": "Aymara",      "order": "SOV"},
    "nav": {"name": "Navajo",      "order": "SOV"},
    "grn": {"name": "Guarani",     "order": "SVO"},
    "nah": {"name": "Nahuatl",     "order": "VSO"}, # Classical

    # --- EUROPE / MIDDLE EAST (Minor / Isolate) ---
    "fry": {"name": "Frisian",     "order": "SVO"},
    "bre": {"name": "Breton",      "order": "SVO"},
    "oci": {"name": "Occitan",     "order": "SVO"},
    "gla": {"name": "Gaelic",      "order": "VSO"}, # Scottish Gaelic
    "cym": {"name": "Welsh",       "order": "VSO"},
    "eus": {"name": "Basque",      "order": "SOV"}, # Fallback
    "tat": {"name": "Tatar",       "order": "SOV"},
    "kur": {"name": "Kurdish",     "order": "SOV"},
}

# Output path matching GF-RGL structure
OUTPUT_ROOT = os.path.join("gf", "generated", "src")

def clean_directory():
    """Wipes the generated directory to ensure a clean build slate."""
    if os.path.exists(OUTPUT_ROOT):
        shutil.rmtree(OUTPUT_ROOT)
    os.makedirs(OUTPUT_ROOT)

# ===========================================================================
# GF TEMPLATES (The "Pidgin" Generator)
# ===========================================================================

def get_res_content(name):
    """
    Generates Res{Lang}.gf
    Defines the minimal type system required for compilation.
    """
    return f"""resource Res{name} = {{
  param
    Number = Sg | Pl ;
  oper
    -- Tier 3 "Pidgin" Type System
    -- We treat everything as simple strings to guarantee compilation.
    -- Complex morphology belongs in Tier 2 (Contrib) or Tier 1 (RGL).
    Noun : Type = {{s : Str}} ;
    Verb : Type = {{s : Str}} ;
    
    -- Smart Constructors
    mkN : Str -> Noun = \\s -> {{s = s}} ;
    mkV : Str -> Verb = \\s -> {{s = s}} ;
}} ;
"""

def get_syntax_content(name, order):
    """
    Generates Syntax{Lang}.gf
    Implements basic word order logic (SVO, SOV, VSO).
    """
    
    # Logic for Subject-Verb-Object (e.g. English, Zulu, Swahili)
    if order == "SVO":
        lin_rule = "subj.s ++ verb.s ++ obj.s"
    
    # Logic for Subject-Object-Verb (e.g. Japanese, Korean, Quechua)
    elif order == "SOV":
        lin_rule = "subj.s ++ obj.s ++ verb.s"
    
    # Logic for Verb-Subject-Object (e.g. Arabic, Welsh, Tagalog)
    elif order == "VSO":
        lin_rule = "verb.s ++ subj.s ++ obj.s"
    
    # Default fallback
    else:
        lin_rule = "subj.s ++ verb.s ++ obj.s"

    return f"""resource Syntax{name} = open Res{name} in {{
  oper
    -- Clause Construction
    mkCl : Noun -> Verb -> Noun -> {{s : Str}} = \\subj, verb, obj -> {{
      s = {lin_rule}
    }} ;
    
    -- Sentence Construction (Add full stop)
    mkS : {{s : Str}} -> {{s : Str}} = \\cl -> {{
      s = cl.s ++ "." 
    }} ;
    
    -- Phrase Casting
    mkNP : Noun -> {{s : Str}} = \\n -> {{s = n.s}} ;
    mkVP : Verb -> {{s : Str}} = \\v -> {{s = v.s}} ;
}} ;
"""

def get_concrete_content(name, abstract_name="AbstractWiki"):
    """
    Generates Wiki{Lang}.gf
    The concrete implementation connecting AbstractWiki to the Syntax module.
    """
    return f"""concrete Wiki{name} of {abstract_name} = open Res{name}, Syntax{name} in {{
  lincat
    Entity = Noun ;
    Predicate = Verb ;
    Fact = {{s : Str}} ;
    Property = {{s : Str}} ;
    Modifier = {{s : Str}} ;
    Value = {{s : Str}} ;

  lin
    -- 1. Fact Construction
    -- We pass an empty string object to simulate intransitive usage if needed
    mkFact subj pred = mkS (mkCl subj pred (mkN "")) ;
    
    -- 2. Property Construction (Is-A)
    -- "Cat is blue" -> Treat "is blue" as a fake verb phrase
    mkIsAProperty subj prop = mkS (mkCl subj (mkV ("IS " ++ prop.s)) (mkN "")) ;

    -- 3. Pass-throughs
    Entity2NP e = e ;
    VP2Predicate v = v ;
    Property2AP p = p ;
    
    -- 4. Literals
    mkLiteral v = mkN v.s ;
    
    -- 5. Modifiers (Simple string append)
    FactWithMod f m = {{s = f.s ++ m.s}} ; 

    -- VOCABULARY STUBS
    -- These ensure the grammar compiles even if we don't have a dictionary yet.
    -- In V2, the AI Refiner will replace these with real words.
    lex_animal_N = mkN "{name}_Animal" ;
    lex_cat_N    = mkN "{name}_Cat" ;
    lex_walk_V   = mkV "{name}_Walk" ;
    lex_blue_A   = mkN "{name}_Blue" ;
}} ;
"""

# ===========================================================================
# MAIN EXECUTION
# ===========================================================================

def main():
    print(f"🏭 Language Factory: Initializing Tier 3 Generation...")
    
    clean_directory()
    
    count = 0
    for code, config in FACTORY_CONFIGS.items():
        name = config["name"]
        order = config["order"]
        
        # GF expects lowercase folder names (e.g. gf/generated/src/zulu/)
        folder_name = name.lower()
        lang_dir = os.path.join(OUTPUT_ROOT, folder_name)
        os.makedirs(lang_dir, exist_ok=True)

        # 1. Write Resource File
        with open(os.path.join(lang_dir, f"Res{name}.gf"), "w", encoding="utf-8") as f:
            f.write(get_res_content(name))
            
        # 2. Write Syntax File
        with open(os.path.join(lang_dir, f"Syntax{name}.gf"), "w", encoding="utf-8") as f:
            f.write(get_syntax_content(name, order))
            
        # 3. Write Concrete Grammar
        with open(os.path.join(lang_dir, f"Wiki{name}.gf"), "w", encoding="utf-8") as f:
            f.write(get_concrete_content(name))

        count += 1

    # Create dummy API folder to satisfy build script generic paths if needed
    api_dir = os.path.join(OUTPUT_ROOT, "api")
    os.makedirs(api_dir, exist_ok=True)

    print(f"✅ Generated {count} language grammars in {OUTPUT_ROOT}")

if __name__ == "__main__":
    main()