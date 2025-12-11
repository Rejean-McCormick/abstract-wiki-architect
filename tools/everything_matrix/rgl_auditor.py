import json
import csv
import os

# Path to the central configuration
CONFIG_PATH = 'config/everything_matrix_config.json'

def load_config():
    """Loads the central configuration."""
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ Config file not found at {CONFIG_PATH}")
        return None
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def audit():
    config = load_config()
    if not config: return

    # Load file paths from config
    inventory_file = config.get("inventory_file", "data/indices/rgl_inventory.json")
    map_file = config.get("map_file", "rgl_map.json")
    exceptions_file = config.get("exceptions_file", "config/language_exceptions.json")
    
    csv_output = config.get("audit_csv", "data/reports/rgl_matrix_audit.csv")
    json_output = config.get("strategy_json", "data/reports/rgl_matrix_strategy.json")

    # Validate inputs
    if not os.path.exists(inventory_file):
        print(f"❌ Error: Inventory file not found at {inventory_file}")
        return

    # LOAD DATA
    with open(inventory_file, 'r') as f:
        inventory = json.load(f).get("languages", {})
    
    with open(map_file, 'r') as f:
        rgl_map = json.load(f).get('module_map', {})

    # LOAD EXCEPTIONS / OVERRIDES
    exceptions = {}
    if os.path.exists(exceptions_file):
        try:
            with open(exceptions_file, 'r') as f:
                exceptions = json.load(f)
            print(f"   Loaded {len(exceptions)} manual overrides.")
        except Exception as e:
            print(f"⚠️ Warning: Could not parse exceptions file: {e}")

    matrix_rows = []
    strategy_map = {}

    print(f"📊 Auditing {len(rgl_map)} languages against RGL Inventory...")

    for wiki_code, rgl_code in rgl_map.items():
        # Initialize Status Block
        status = {
            "Wiki": wiki_code, 
            "RGL": rgl_code,
            "Cat": "MISSING", 
            "Noun": "MISSING", 
            "Grammar": "MISSING", 
            "Syntax": "MISSING",
            "Strategy": "SKIP",
            "Note": ""
        }

        # --- CHECK MANUAL OVERRIDES FIRST ---
        if wiki_code in exceptions:
            override = exceptions[wiki_code]
            status["Strategy"] = override.get("override_strategy", "BROKEN")
            status["Note"] = f"OVERRIDE: {override.get('reason', 'Manual exclusion')}"
            
            # If manually broken, we stop processing this language
            if status["Strategy"] == "BROKEN":
                matrix_rows.append(status)
                continue

        # Check against Inventory (Auto-Detection)
        if rgl_code in inventory:
            data = inventory[rgl_code]
            modules = data.get("modules", {})
            
            if "Cat" in modules: status["Cat"] = "FOUND"
            if "Noun" in modules: status["Noun"] = "FOUND"
            if "Grammar" in modules: status["Grammar"] = "FOUND"
            if "Syntax" in modules: status["Syntax"] = "FOUND"

            # --- DECISION ENGINE ---
            
            # If an override set a strategy (like SAFE_MODE) explicitly, we respect it 
            # BUT we still verify if the files exist. 
            # If no override, we calculate normally.
            
            forced_strat = exceptions.get(wiki_code, {}).get("override_strategy")

            if forced_strat:
                status["Strategy"] = forced_strat
            else:
                # STRATEGY A: HIGH_ROAD (Standard RGL)
                if (status["Cat"] == "FOUND" and 
                    status["Noun"] == "FOUND" and 
                    status["Grammar"] == "FOUND" and 
                    status["Syntax"] == "FOUND"):
                    status["Strategy"] = "HIGH_ROAD"
                
                # STRATEGY B: SAFE_MODE (Fallback)
                elif status["Cat"] == "FOUND" and status["Noun"] == "FOUND":
                    status["Strategy"] = "SAFE_MODE"
                
                # STRATEGY C: BROKEN
                else:
                    status["Strategy"] = "BROKEN"
        
        else:
            status["Strategy"] = "NOT_INSTALLED"

        # Add to CSV list
        matrix_rows.append(status)
        
        # Add to JSON Map (Instructions for Builder)
        if status["Strategy"] in ["HIGH_ROAD", "SAFE_MODE"]:
            strategy_map[wiki_code] = {
                "rgl_code": rgl_code,
                "strategy": status["Strategy"],
                "modules": inventory.get(rgl_code, {}).get("modules", {}),
                "path_root": inventory.get(rgl_code, {}).get("path")
            }

    # Write CSV Report
    os.makedirs(os.path.dirname(csv_output), exist_ok=True)
    with open(csv_output, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["Wiki", "RGL", "Cat", "Noun", "Grammar", "Syntax", "Strategy", "Note"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matrix_rows)

    # Write Executable Strategy Map
    os.makedirs(os.path.dirname(json_output), exist_ok=True)
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(strategy_map, f, indent=2)

    print(f"✅ Audit Complete.")
    print(f"   Human Report: {csv_output}")
    print(f"   Builder Map:  {json_output}")
    print(f"   Buildable Languages: {len(strategy_map)}")

if __name__ == "__main__":
    audit()