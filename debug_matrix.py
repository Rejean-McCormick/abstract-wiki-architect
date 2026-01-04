import sys
import json
from pathlib import Path

# Setup paths
BASE_DIR = Path.cwd()
sys.path.append(str(BASE_DIR / "tools" / "everything_matrix"))

try:
    from scoring import choose_build_strategy, zone_a_from_modules
    from norm import load_iso_to_wiki, build_wiki_to_iso2, norm_to_iso2
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def debug_english():
    print("=== DEBUGGING ENGLISH (en) STRATEGY ===")
    
    # 1. Check ISO Mapping
    iso_map_file = BASE_DIR / "data/config/iso_to_wiki.json"
    iso_data = load_iso_to_wiki(iso_map_file)
    wiki_to_iso = build_wiki_to_iso2(iso_data)
    
    normalized = norm_to_iso2("en", wiki_to_iso2=wiki_to_iso)
    print(f"1. Normalization: 'en' -> '{normalized}'")
    
    # 2. Check RGL Inventory on Disk
    rgl_file = BASE_DIR / "data/indices/rgl_inventory.json"
    if not rgl_file.exists():
        print("❌ rgl_inventory.json NOT FOUND")
        return

    try:
        rgl_data = json.loads(rgl_file.read_text())
        langs = rgl_data.get("languages", {})
        en_rec = langs.get("en") or langs.get("eng")
        
        print(f"2. RGL Data for 'en': {'FOUND' if en_rec else 'MISSING'}")
        if en_rec:
            modules = en_rec.get("modules", {})
            print(f"   Modules found: {list(modules.keys())}")
            
            zone_a = zone_a_from_modules(modules)
            print(f"   Calculated Zone A: {zone_a}")
        else:
            zone_a = {}
    except Exception as e:
        print(f"❌ Error reading RGL inventory: {e}")
        return

    # 3. Simulate Decision
    # Mocking other zones to isolate the RGL factor
    mock_zone_b = {"SEED": 10.0} # Assume valid lexicon
    mock_zone_d = {"BIN": 0.0}
    mock_registry = {}
    mock_config = {
        "high_road": {"min_maturity": 4.0, "min_cat": 10.0, "min_seed": 2.0},
        "skip": {"min_a_avg": 2.0}
    }
    
    strategy = choose_build_strategy(
        iso2="en",
        maturity_score=8.0, # Mock high score
        zone_a=zone_a,
        zone_b=mock_zone_b,
        zone_d=mock_zone_d,
        factory_registry=mock_registry,
        cfg_matrix=mock_config
    )
    
    print(f"4. FINAL VERDICT: {strategy}")

if __name__ == "__main__":
    debug_english()