import os
import json
import sys
import datetime
import subprocess

# Ensure we can import sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import rgl_scanner
import rgl_auditor
import lexicon_scanner
import app_scanner

CONFIG_PATH = 'config/everything_matrix_config.json'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Config file not found at {CONFIG_PATH}")
        return None
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def get_compiled_languages(pgf_path="Wiki.pgf"):
    if not os.path.exists(pgf_path):
        return set()
    try:
        result = subprocess.run(
            ["gf", "--show-langs", pgf_path], 
            capture_output=True, text=True, check=True
        )
        langs = result.stdout.strip().split()
        return {l.replace("Wiki", "") for l in langs}
    except Exception as e:
        return set()

def build_index():
    config = load_config()
    if not config: return

    print("🚀 STARTING EVERYTHING MATRIX BUILD...")

    # --- STEP 1: RUN SUB-SCANNERS ---
    print("\n--- [1/4] Running RGL Scanners ---")
    rgl_scanner.scan_rgl()
    rgl_auditor.audit()

    print("\n--- [2/4] Running Data Scanners ---")
    lex_data_raw = lexicon_scanner.scan_lexicon()
    app_data_raw = app_scanner.scan_application()

    # --- STEP 2: LOAD DATA ---
    print("\n--- [3/4] Aggregating Data ---")
    
    # Load RGL Inventory
    inventory_file = config.get("inventory_file", "data/indices/rgl_inventory.json")
    with open(inventory_file, 'r') as f:
        rgl_inventory = json.load(f).get("languages", {})

    # Load Strategy Map
    strategy_file = config.get("strategy_json", "data/reports/rgl_matrix_strategy.json")
    strategy_map = {}
    if os.path.exists(strategy_file):
        with open(strategy_file, 'r') as f:
            strategy_map = json.load(f)

    # Load Module Map
    map_file = config.get("map_file", "rgl_map.json")
    with open(map_file, 'r') as f:
        rgl_map_data = json.load(f)
        module_map = rgl_map_data.get("module_map", {})
    
    # Load Build Failures (The "Self-Healing" Report)
    failure_report = "data/reports/build_failures.json"
    failures = {}
    if os.path.exists(failure_report):
        with open(failure_report, 'r') as f:
            failures = json.load(f)
        print(f"   Loaded {len(failures)} build failures.")

    # --- LOAD ISO MAPPING ---
    iso_map_file = config.get("iso_map_file", "config/iso_to_wiki.json")
    iso_to_wiki = {}
    if os.path.exists(iso_map_file):
        with open(iso_map_file, 'r') as f:
            iso_to_wiki = json.load(f)
        print(f"   Loaded {len(iso_to_wiki)} ISO mappings.")
    else:
        print(f"⚠️ Warning: ISO Map file missing at {iso_map_file}")

    # Helper: Normalize Data Keys
    def normalize_keys(data_dict):
        new_dict = {}
        for k, v in data_dict.items():
            # Convert 'en' -> 'Eng' using map, default to self if not found
            norm_k = iso_to_wiki.get(k.lower(), iso_to_wiki.get(k, k))
            # Capitalize if it looks like a wiki code (3 chars) but wasn't in map
            if len(norm_k) == 3: norm_k = norm_k.capitalize()

            if norm_k not in new_dict:
                new_dict[norm_k] = {}
            new_dict[norm_k].update(v)
        return new_dict

    # Normalize Scanned Data
    lex_data = normalize_keys(lex_data_raw)
    app_data = normalize_keys(app_data_raw)

    # Check Compilation
    compiled_langs = get_compiled_languages("Wiki.pgf")

    # --- STEP 3: BUILD MATRIX ---
    master_index = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "languages": {}
    }

    all_codes = set(module_map.keys()) | set(lex_data.keys()) | set(app_data.keys()) | set(rgl_inventory.keys())

    for wiki_code in sorted(list(all_codes)):
        # Normalize code again just to be safe (e.g. ensure 'Eng' not 'eng')
        if len(wiki_code) == 3: wiki_code = wiki_code.capitalize()
        
        rgl_code = module_map.get(wiki_code, wiki_code)
        
        entry = {
            "meta": {
                "wiki_code": wiki_code,
                "rgl_code": rgl_code,
                "iso_code": "???", 
                "name": wiki_code
            },
            "blocks": {},
            "status": {}
        }

        # RGL Scores
        rgl_data = rgl_inventory.get(rgl_code, {}).get("modules", {})
        entry["blocks"]["rgl_cat"] = 10 if "Cat" in rgl_data else 0
        entry["blocks"]["rgl_noun"] = 10 if "Noun" in rgl_data else 0
        entry["blocks"]["rgl_paradigms"] = 10 if "Paradigms" in rgl_data else 0
        entry["blocks"]["rgl_grammar"] = 10 if "Grammar" in rgl_data else 0
        entry["blocks"]["rgl_syntax"] = 10 if "Syntax" in rgl_data else 0

        # Lexicon Scores
        l_data = lex_data.get(wiki_code, {})
        entry["blocks"]["lex_seed"] = l_data.get("lex_seed", 0)
        entry["blocks"]["lex_concrete"] = l_data.get("lex_concrete", 0)
        entry["blocks"]["lex_wide"] = l_data.get("lex_wide", 0)
        entry["blocks"]["sem_mappings"] = l_data.get("sem_mappings", 0)

        # App Scores
        a_data = app_data.get(wiki_code, {})
        entry["blocks"]["app_profile"] = a_data.get("app_profile", 0)
        entry["blocks"]["app_assets"] = a_data.get("app_assets", 0)
        entry["blocks"]["app_routes"] = a_data.get("app_routes", 0)
        
        # Quality Scores (Build Config + Failures)
        strat = strategy_map.get(wiki_code, {}).get("strategy", "NONE")
        
        # [CRITICAL UPDATE]: Check if this language is in the Failure Report
        if wiki_code in failures:
            strat = "BROKEN"
            entry["status"]["error_message"] = failures[wiki_code].get("reason", "Unknown build error")
            entry["blocks"]["build_config"] = 2 # Red flag for failure
        elif strat == "HIGH_ROAD":
            entry["blocks"]["build_config"] = 10
        elif strat == "SAFE_MODE":
            entry["blocks"]["build_config"] = 5
        else:
            entry["blocks"]["build_config"] = 0

        entry["blocks"]["meta_compile"] = 10 if wiki_code in compiled_langs else 0
        entry["blocks"]["meta_test"] = 0 

        # Overall Status
        values = list(entry["blocks"].values())
        maturity = sum(values) / len(values) if values else 0
        
        entry["status"]["build_strategy"] = strat
        entry["status"]["overall_maturity"] = round(maturity, 1)
        entry["status"]["is_active"] = (entry["blocks"]["meta_compile"] == 10)

        master_index["languages"][wiki_code] = entry

    # --- STEP 4: WRITE TO DISK ---
    output_path = config.get("everything_index", "data/indices/everything_matrix.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(master_index, f, indent=2)

    print(f"\n✅ EVERYTHING MATRIX BUILT: {output_path}")
    print(f"   Total Languages: {len(master_index['languages'])}")
    print(f"   Compiled/Active: {len(compiled_langs)}")

if __name__ == "__main__":
    build_index()