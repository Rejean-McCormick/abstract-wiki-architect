import os
import json

# Path to the central configuration
CONFIG_PATH = 'config/everything_matrix_config.json'

def load_config():
    """Loads the central configuration or returns safe defaults."""
    if not os.path.exists(CONFIG_PATH):
        print(f"⚠️ Config not found at {CONFIG_PATH}, using defaults.")
        return {
            "rgl_base_path": "gf-rgl/src",
            "inventory_file": "data/indices/rgl_inventory.json",
            "ignored_folders": ["doc", "examples", "dist", "bin", "boot"]
        }
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def scan_rgl():
    config = load_config()
    
    # Extract paths from config
    base_path = config.get("rgl_base_path", "gf-rgl/src")
    output_file = config.get("inventory_file", "data/indices/rgl_inventory.json")
    ignored_folders = set(config.get("ignored_folders", []))
    
    print(f"🔍 Scanning {base_path} for RGL modules...")
    
    inventory = {}
    family_folders = set()

    # Walk through every folder in RGL
    for root, dirs, files in os.walk(base_path):
        folder_name = os.path.basename(root)
        
        # Skip ignored folders
        if folder_name in ignored_folders:
            continue

        # Filter for GF files only
        gf_files_in_folder = [f for f in files if f.endswith(".gf")]
        if not gf_files_in_folder:
            continue

        is_language_folder = False

        for file in gf_files_in_folder:
            # Normalize path for cross-platform compatibility (Windows/Linux)
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, start='.')
            norm_path = rel_path.replace("\\", "/")
            
            name_part = file.replace(".gf", "")
            
            module_type = None
            lang_code = None

            # --- DETECT MODULE TYPES ---
            if name_part.startswith("Grammar"):
                module_type = "Grammar"
                lang_code = name_part.replace("Grammar", "")
            elif name_part.startswith("Cat"):
                module_type = "Cat"
                lang_code = name_part.replace("Cat", "")
            elif name_part.startswith("Noun"):
                module_type = "Noun"
                lang_code = name_part.replace("Noun", "")
            elif name_part.startswith("Paradigms"):
                module_type = "Paradigms"
                lang_code = name_part.replace("Paradigms", "")
            elif name_part.startswith("Syntax"): 
                # CRITICAL: Detect Syntax modules for 'High Road' eligibility
                module_type = "Syntax"
                lang_code = name_part.replace("Syntax", "")
            
            # --- LOGIC 1: DETECT LANGUAGES (3-letter codes) ---
            if module_type and len(lang_code) == 3:
                is_language_folder = True
                if lang_code not in inventory:
                    inventory[lang_code] = {"path": root, "modules": {}}
                
                inventory[lang_code]["modules"][module_type] = norm_path
            
            # --- LOGIC 2: DETECT FAMILIES (Code > 3 letters) ---
            # e.g. GrammarRomance -> Code "Romance" -> Family
            if lang_code and len(lang_code) > 3:
                 family_folders.add(folder_name)

        # --- LOGIC 3: FALLBACK FAMILY DETECTION ---
        # If a folder contains GF files but isn't a 3-letter language folder,
        # it is likely a shared family folder (e.g. 'romance', 'common', 'api').
        if not is_language_folder and folder_name not in ignored_folders:
            if not folder_name.startswith("."):
                family_folders.add(folder_name)

    # Prepare Output Data
    final_data = {
        "languages": inventory,
        "families": sorted(list(family_folders))
    }

    # Write to Disk
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(final_data, f, indent=2)
    
    print(f"✅ Inventory saved to {output_file}")
    print(f"   Languages found: {len(inventory)}")
    print(f"   Families/Shared folders detected: {len(family_folders)}")

if __name__ == "__main__":
    scan_rgl()