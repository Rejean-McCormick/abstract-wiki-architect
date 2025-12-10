import os
import json
import shutil

# --- Configuration ---
# We try to detect if you have a backup folder named "-lexicon"
POTENTIAL_SOURCES = [
    os.path.join("data", "-lexicon"),  # Check the folder with the dash first
    os.path.join("data", "lexicon")    # Then check the standard folder
]
TARGET_DIR = os.path.join("data", "lexicon")

# Map legacy keys to new domain filenames
DOMAIN_MAP = {
    "professions": "people",
    "titles": "people",
    "honours": "people",
    "nationalities": "geography",
    "tags": {
        "science": "science",
        "physics": "science",
        "chemistry": "science",
        "biology": "science",
        "mathematics": "science",
        "politics": "people",
        "profession": "people",
        "title": "people",
        "human": "people",
        "geography": "geography",
        "country": "geography",
        "city": "geography",
        "nationality": "geography",
        "demonym": "geography",
        "core": "core"
    }
}

def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return None

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_target_domain(key, entry):
    """Decide which domain (core, people, science, geo) an entry belongs to."""
    # 1. Check tags
    tags = []
    if "semantic_field" in entry: tags.append(entry["semantic_field"])
    if "semantic_class" in entry: tags.append(entry["semantic_class"])
    if "category" in entry: tags.append(entry["category"])
    
    for tag in tags:
        if tag in DOMAIN_MAP["tags"]:
            return DOMAIN_MAP["tags"][tag]

    # 2. Heuristics
    if entry.get("nationality") or (entry.get("proper_name") and entry.get("semantic_class") in ["city", "country"]):
        return "geography"
    
    if "physic" in key or "chem" in key or "math" in key:
        return "science"
        
    return "core"

def migrate_file(source_dir, filename):
    # Skip non-data files
    if filename in ["schema.json", "lexicon_schema.json", "package.json"]:
        return

    lang_code = filename.split("_")[0] # e.g. 'fr' from 'fr_lexicon.json'
    
    # Handle files like 'en_core.json' where 'en' is the code
    if len(lang_code) > 3: 
        # Fallback for weird names: try to detect if it starts with a known code
        if "_" in filename:
            lang_code = filename.split("_")[0]
        else:
            print(f"Skipping unrecognized filename format: {filename}")
            return

    src_path = os.path.join(source_dir, filename)
    data = load_json(src_path)
    if not data: return

    print(f"Processing {lang_code.upper()} from {filename}...")

    # Ensure target directory exists (e.g. data/lexicon/fr/)
    lang_dir = os.path.join(TARGET_DIR, lang_code)
    os.makedirs(lang_dir, exist_ok=True)

    # Prepare buckets
    new_data = { d: {} for d in ["core", "people", "science", "geography"] }
    migrated_count = 0

    # Strategy 1: Nested Categories (e.g., "professions": {...})
    for cat in ["professions", "titles", "honours", "nationalities"]:
        if cat in data:
            target = DOMAIN_MAP.get(cat, "core")
            for k, v in data[cat].items():
                new_data[target][k] = v
                migrated_count += 1

    # Strategy 2: Flat List (e.g., "lemmas": {...} or root dict)
    root_keys = ["lemmas", "entries"]
    found_root = False
    for r in root_keys:
        if r in data:
            found_root = True
            for k, v in data[r].items():
                target = get_target_domain(k, v)
                new_data[target][k] = v
                migrated_count += 1
    
    # Strategy 3: Pure Key-Value at root
    if not found_root and migrated_count == 0:
        # Check if it looks like a dictionary of entries
        if "meta" not in data and "_meta" not in data:
            for k, v in data.items():
                if isinstance(v, dict) and "pos" in v:
                    target = get_target_domain(k, v)
                    new_data[target][k] = v
                    migrated_count += 1

    # Write to destination
    for domain, entries in new_data.items():
        if not entries: continue
        
        dest_file = os.path.join(lang_dir, f"{domain}.json")
        
        # Load existing if present (from scaffold)
        existing_content = {"entries": {}}
        if os.path.exists(dest_file):
            existing_content = load_json(dest_file) or {"entries": {}}
            if "entries" not in existing_content:
                existing_content = {"entries": existing_content}

        # Merge
        existing_content.setdefault("entries", {}).update(entries)
        
        # Ensure Meta
        if "_meta" not in existing_content:
            existing_content["_meta"] = {
                "language": lang_code,
                "domain": domain,
                "version": 2
            }
            
        save_json(dest_file, existing_content)
    
    print(f"  -> Migrated {migrated_count} entries.")

def main():
    # 1. Determine Source Directory
    source_dir = None
    files = []
    
    print(f"Current Working Directory: {os.getcwd()}")
    
    for path in POTENTIAL_SOURCES:
        if os.path.exists(path):
            candidates = [f for f in os.listdir(path) if f.endswith(".json")]
            # Check if this folder actually has lexicon files (not just subfolders)
            if any(os.path.isfile(os.path.join(path, f)) for f in candidates):
                source_dir = path
                files = candidates
                print(f"Found source files in: {source_dir}")
                break
    
    if not source_dir or not files:
        print("\n[ERROR] Could not find legacy .json files in 'data/lexicon' or 'data/-lexicon'.")
        print("Please ensure your old files are in one of those folders.")
        return

    # 2. Run Migration
    print(f"Found {len(files)} files to process.")
    for f in files:
        # Skip directories
        if os.path.isdir(os.path.join(source_dir, f)):
            continue
        migrate_file(source_dir, f)

    print("\nMigration Complete.")

if __name__ == "__main__":
    main()