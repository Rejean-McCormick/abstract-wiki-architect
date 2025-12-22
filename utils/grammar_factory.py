# utils/grammar_factory.py
import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

# ===========================================================================
# CONFIGURATION & PATHS
# ===========================================================================

# Base Paths (Hybrid WSL/Windows Compatible)
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = BASE_DIR / "gf" / "generated" / "src"
CONFIG_DIR = BASE_DIR / "data" / "config"

TOPOLOGY_WEIGHTS_PATH = CONFIG_DIR / "topology_weights.json"
FACTORY_TARGETS_PATH = CONFIG_DIR / "factory_targets.json"

# ===========================================================================
# LOGIC CLASS
# ===========================================================================

class GrammarFactory:
    def __init__(self):
        # Load Rules (SVO, SOV definitions)
        self.weights_db = self._load_json(TOPOLOGY_WEIGHTS_PATH, default={"SVO": {"nsubj": -10, "root": 0, "obj": 10}})
        # Load Blueprint (Which languages to build)
        self.targets_db = self._load_json(FACTORY_TARGETS_PATH, default={})

    def _load_json(self, path: Path, default: Dict) -> Dict:
        """Helper to load JSON config safely."""
        if not path.exists():
            print(f"[!] Warning: Config not found at {path}")
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[!] Error: Corrupt JSON at {path}")
            return default

    def get_target_config(self, iso_code: str) -> Dict:
        """Retrieves name and topology order for a language."""
        return self.targets_db.get(iso_code, {"name": iso_code, "order": "SVO"})

    def create_concrete(self, iso_code: str, order: str = None) -> str:
        """
        Public API: Generates the full concrete grammar content string.
        """
        target_meta = self.get_target_config(iso_code)
        
        human_name = target_meta.get("name", iso_code)
        # If order is not provided, look it up in targets, fallback to SVO
        if not order:
            order = target_meta.get("order", "SVO")
            
        gf_name = iso_code.capitalize()
        
        # Ensure directories exist
        out_dir = OUTPUT_ROOT / iso_code.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Write Res
        with open(out_dir / f"Res{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(get_res_content(gf_name))
            
        # 2. Write Syntax
        with open(out_dir / f"Syntax{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(get_syntax_content(gf_name, order, self.weights_db))
            
        # 3. Return Concrete Content (Caller will write this usually, but we return it)
        return get_concrete_content(gf_name, human_name)

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
    Generates Res{Lang}.gf - Minimal Type System
    """
    return f"""resource Res{gf_name} = {{
  param
    Number = Sg | Pl ;

  oper
    -- Tier 3 "Pidgin" Type System
    StrType : Type = {{s : Str}} ;
    mkStrType : Str -> StrType = \\s -> {{s = s}} ;
    combine : StrType -> StrType -> StrType = \\a,b -> {{ s = a.s ++ b.s }} ;
}} ;
"""

def get_syntax_content(gf_name: str, order_key: str, weights_db: Dict) -> str:
    """
    Generates Syntax{Lang}.gf using Weighted Topology Sorting.
    """
    weights = weights_db.get(order_key, weights_db.get("SVO"))
    
    # Keys must match topology_weights.json
    constituents = [
        {"gf_var": "subj", "role": "nsubj", "weight": weights.get("nsubj", -10)},
        {"gf_var": "verb", "role": "root",  "weight": weights.get("root", 0)},
        {"gf_var": "obj",  "role": "obj",   "weight": weights.get("obj", 10)}
    ]
    
    # Sort by weight (Low -> High = Left -> Right)
    sorted_constituents = sorted(constituents, key=lambda x: x["weight"])
    lin_parts = [f"{item['gf_var']}.s" for item in sorted_constituents]
    lin_rule = " ++ ".join(lin_parts)

    return f"""resource Syntax{gf_name} = open Res{gf_name} in {{
  oper
    -- Clause Construction (Weighted Topology: {order_key})
    mkCl : StrType -> StrType -> StrType -> {{s : Str}} = \\subj, verb, obj -> {{
      s = {lin_rule}
    }} ;
    
    mkS : {{s : Str}} -> {{s : Str}} = \\cl -> {{ s = cl.s ++ "." }} ;
    mkNP : StrType -> {{s : Str}} = \\n -> {{s = n.s}} ;
    mkVP : StrType -> {{s : Str}} = \\v -> {{s = v.s}} ;
}} ;
"""

def get_concrete_content(gf_name, human_name, abstract_name="AbstractWiki"):
    """
    Generates Wiki{Lang}.gf - The Concrete Implementation
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
    mkFact s p = mkS (mkCl s p (mkStrType "")) ;
    mkIsAProperty s p = mkS (mkCl s (mkStrType ("IS " ++ p.s)) (mkStrType "")) ;
    
    Entity2NP e = e ;
    VP2Predicate v = v ;
    Property2AP p = p ;
    mkLiteral v = mkStrType v.s ;
    FactWithMod f m = {{s = f.s ++ m.s}} ; 

    -- VOCABULARY STUBS (To be replaced by Lexicon/AI)
    lex_animal_N = mkStrType "{human_name}_Animal" ;
    lex_cat_N    = mkStrType "{human_name}_Cat" ;
    lex_walk_V   = mkStrType "{human_name}_Walk" ;
    lex_blue_A   = mkStrType "{human_name}_Blue" ;
}} ;
"""

# ===========================================================================
# MAIN EXECUTION (CLI MODE)
# ===========================================================================

def main():
    print(f"🏭 Language Factory: Initializing Tier 3 Generation...")
    
    factory = GrammarFactory()
    clean_directory()
    
    count = 0
    # Iterate over the loaded JSON targets
    for code, config in factory.targets_db.items():
        human_name = config.get("name", code)
        order = config.get("order", "SVO")
        gf_name = code.capitalize()
        
        # Write helper files (Res/Syntax)
        factory.create_concrete(code, order)
        
        # Write main file
        lang_dir = OUTPUT_ROOT / code.lower()
        concrete_content = get_concrete_content(gf_name, human_name)
        with open(lang_dir / f"Wiki{gf_name}.gf", "w", encoding="utf-8") as f:
            f.write(concrete_content)

        count += 1

    # Create dummy API folder
    api_dir = OUTPUT_ROOT / "api"
    api_dir.mkdir(exist_ok=True)

    print(f"✅ Generated {count} language grammars in {OUTPUT_ROOT}")
    print(f"[*] Run 'manage.py build' next to compile the PGF.")

if __name__ == "__main__":
    main()