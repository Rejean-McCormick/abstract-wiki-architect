import json
import os
import shutil
import re
from pathlib import Path

# Paths
BASE_DIR = Path.cwd()
SRC_DIR = BASE_DIR / "gf" / "generated" / "src"
CONFIG_FILE = BASE_DIR / "data" / "config" / "iso_to_wiki.json"

def smart_rename_and_patch():
    if not CONFIG_FILE.exists():
        print("❌ Config file not found.")
        return

    print("📖 Reading ISO mapping...")
    with open(CONFIG_FILE, 'r') as f:
        iso_map = json.load(f)

    # Map { "zho": "Chi", "ell": "Gre", ... }
    valid_renames = {}
    for iso_key, data in iso_map.items():
        if isinstance(data, dict) and "wiki" in data:
            wiki_code = data["wiki"]
            valid_renames[iso_key.lower()] = wiki_code
            valid_renames[wiki_code.lower()] = wiki_code

    print(f"🔍 Scanning and Patching {SRC_DIR}...")
    count = 0
    
    for file_path in SRC_DIR.glob("Wiki*.gf"):
        original_stem = file_path.stem # e.g. WikiEll
        if len(original_stem) <= 4: continue
        
        current_suffix = original_stem[4:].lower() # "ell"
        
        if current_suffix in valid_renames:
            correct_suffix = valid_renames[current_suffix] # "Gre"
            new_stem = f"Wiki{correct_suffix}"
            new_name = f"{new_stem}.gf"
            
            # 1. Rename File if needed
            target_path = SRC_DIR / new_name
            if file_path.name != new_name:
                print(f"🔄 Renaming: {file_path.name} -> {new_name}")
                shutil.move(file_path, target_path)
                file_path = target_path # Update ref

            # 2. Patch Content
            # We need to change "concrete WikiEll of" to "concrete WikiGre of"
            try:
                content = file_path.read_text(encoding="utf-8")
                
                # Regex to find module definition
                # Matches: concrete WikiEll of ...
                pattern = re.compile(rf"concrete\s+{original_stem}\s+of", re.IGNORECASE)
                
                if pattern.search(content):
                    new_content = pattern.sub(f"concrete {new_stem} of", content)
                    if new_content != content:
                        file_path.write_text(new_content, encoding="utf-8")
                        print(f"   ✨ Patched module name in {new_name}")
                        count += 1
            except Exception as e:
                print(f"   ❌ Error patching {file_path.name}: {e}")

    print(f"✅ Operations complete. Patched {count} files.")

if __name__ == "__main__":
    smart_rename_and_patch()