import os
import shutil
from pathlib import Path

# ===========================================================================
# LANGUAGE FACTORY CONFIGURATION (TIER 3)
# ===========================================================================
# This dictionary defines the "DNA" for languages that do not exist in the
# official Resource Grammar Library.
#
# Schema: "iso_code": { "name": "EnglishName", "order": "SVO"|"SOV"|"VSO" }
# ===========================================================================

FACTORY_CONFIGS = {
    # --- AFRICA (Bantu / Niger-Congo / Afroasiatic) ---
    "zul": {"name": "Zulu",        "order": "SVO"},
    "xho": {"name": "Xhosa",       "order": "SVO"},
    "yor": {"name": "Yoruba",      "order": "SVO"},
    "ibo": {"name": "Igbo",        "order": "SVO"},
    "hau": {"name": "Hausa",       "order": "SVO"},
    "swa": {"name": "Swahili",     "order": "SVO"}, # Fallback
    "wol": {"name": "Wolof",       "order": "SVO"},
    "kin": {"name": "Kinyarwanda", "order": "SVO"},
    "lug": {"name": "Ganda",       "order": "SVO"},
    "lin": {"name": "Lingala",     "order": "SVO"},
    "som": {"name": "Somali",      "order": "SOV"}, 

    # --- ASIA (Austronesian / Dravidian / Turkic) ---
    "kor": {"name": "Korean",      "order": "SOV"},
    "ind": {"name": "Indonesian",  "order": "SVO"},
    "msa": {"name": "Malay",       "order": "SVO"},
    "tgl": {"name": "Tagalog",     "order": "VSO"}, 
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
    "nah": {"name": "Nahuatl",     "order": "VSO"}, 

    # --- EUROPE / MIDDLE EAST (Minor / Isolate) ---
    "fry": {"name": "Frisian",     "order": "SVO"},
    "bre": {"name": "Breton",      "order": "SVO"}, 
    "oci": {"name": "Occitan",     "order": "SVO"},
    "gla": {"name": "Gaelic",      "order": "VSO"}, 
    "cym": {"name": "Welsh",       "order": "VSO"},
    "eus": {"name": "Basque",      "order": "SOV"}, 
    "tat": {"name": "Tatar",       "order": "SOV"},
    "kur": {"name": "Kurdish",     "order": "SOV"},
}

# Determine the absolute path to 'gf/generated/src' based on this script's location
# This ensures it works whether run from root or inside utils/
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = BASE_DIR / "gf" / "generated" / "src"

def clean_directory():
    """Wipes the generated directory to ensure a clean build slate."""
    if OUTPUT_ROOT.exists():
        print(f"[*] Cleaning factory output: {OUTPUT_ROOT}")
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# ===========================================================================
# GF TEMPLATES (The "Pidgin" Generator)
# ===========================================================================

def get_res_content(gf_name):
    """
    Generates Res{Lang}.gf
    Defines the minimal type system required for compilation.
    """
    return f"""resource Res{gf_name} = {{
  param
    Number = Sg | Pl ;

  oper
    -- Tier 3 "Pidgin" Type System
    -- We treat everything as simple strings to guarantee compilation.
    -- Complex morphology belongs in Tier 2 (Contrib) or Tier 1 (RGL).
    StrType : Type = {{s : Str}} ;

    mkStrType : Str -> StrType = \\s -> {{s = s}} ;

    -- Simple string concatenation helper
    combine : StrType -> StrType -> StrType = \\a,b -> 
      {{ s = a.s ++ b.s }} ;
}} ;
"""

def get_syntax_content(gf_name, order):
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

    return f"""resource Syntax{gf_name} = open Res{gf_name} in {{
  oper
    -- Clause Construction
    mkCl : StrType -> StrType -> StrType -> {{s : Str}} = \\subj, verb, obj -> {{
      s = {lin_rule}
    }} ;
    
    -- Sentence Construction (Add full stop)
    mkS : {{s : Str}} -> {{s : Str}} = \\cl -> {{
      s = cl.s ++ "." 
    }} ;
    
    -- Phrase Casting (Identity functions for Pidgin)
    mkNP : StrType -> {{s : Str}} = \\n -> {{s = n.s}} ;
    mkVP : StrType -> {{s : Str}} = \\v -> {{s = v.s}} ;
}} ;
"""

def get_concrete_content(gf_name, human_name, abstract_name="AbstractWiki"):
    """
    Generates Wiki{Lang}.gf
    The concrete implementation connecting AbstractWiki to the Syntax module.
    """
    return f"""-- Generated by Grammar Factory for {human_name} ({gf_name})
concrete Wiki{gf_name} of {abstract_name} = open Res{gf_name}, Syntax{gf_name} in {{

  lincat
    Entity = StrType ;
    Predicate = StrType ;
    Fact = {{s : Str}} ;
    Property = StrType ;
    Modifier = StrType ;
    Value = StrType ;

  lin
    -- 1. Fact Construction
    -- We pass an empty string object to simulate intransitive usage if needed
    mkFact subj pred = mkS (mkCl subj pred (mkStrType "")) ;
    
    -- 2. Property Construction (Is-A)
    -- "Cat is blue" -> Treat "is blue" as a fake verb phrase
    mkIsAProperty subj prop = mkS (mkCl subj (mkStrType ("IS " ++ prop.s)) (mkStrType "")) ;

    -- 3. Pass-throughs
    Entity2NP e = e ;
    VP2Predicate v = v ;
    Property2AP p = p ;
    
    -- 4. Literals
    mkLiteral v = mkStrType v.s ;
    
    -- 5. Modifiers (Simple string append)
    FactWithMod f m = {{s = f.s ++ m.s}} ; 

    -- VOCABULARY STUBS
    -- These ensure the grammar compiles even if we don't have a dictionary yet.
    -- In V2, the AI Refiner will replace these with real words.
    lex_animal_N = mkStrType "{human_name}_Animal" ;
    lex_cat_N    = mkStrType "{human_name}_Cat" ;
    lex_walk_V   = mkStrType "{human_name}_Walk" ;
    lex_blue_A   = mkStrType "{human_name}_Blue" ;
}} ;
"""

# ===========================================================================
# MAIN EXECUTION
# ===========================================================================

def main():
    print(f"🏭 Language Factory: Initializing Tier 3 Generation...")
    print(f"[*] Target Directory: {OUTPUT_ROOT}")
    
    clean_directory()
    
    count = 0
    for code, config in FACTORY_CONFIGS.items():
        human_name = config["name"]
        order = config["order"]
        
        # IMPORTANT: Map the ISO code to the GF Name Convention (WikiZul, not WikiZulu)
        # to match the Router's logic in language_map.py.
        gf_name = code.capitalize()  # zul -> Zul
        
        # GF expects lowercase folder names (e.g. gf/generated/src/zul/)
        # This mirrors the structure of gf-rgl/src/
        folder_name = code.lower()
        lang_dir = OUTPUT_ROOT / folder_name
        lang_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write Resource File
        with open(lang_dir / f"Res{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(get_res_content(gf_name))
            
        # 2. Write Syntax File
        with open(lang_dir / f"Syntax{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(get_syntax_content(gf_name, order))
            
        # 3. Write Concrete Grammar
        with open(lang_dir / f"Wiki{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(get_concrete_content(gf_name, human_name))

        count += 1

    # Create dummy API folder to satisfy build script generic paths if needed
    api_dir = OUTPUT_ROOT / "api"
    api_dir.mkdir(exist_ok=True)

    print(f"✅ Generated {count} language grammars in {OUTPUT_ROOT}")
    print(f"[*] Run 'gf/build_orchestrator.py' next to compile the PGF.")

if __name__ == "__main__":
    main()