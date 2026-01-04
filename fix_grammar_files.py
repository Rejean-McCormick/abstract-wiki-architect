import os
import re
from pathlib import Path

# Paths
BASE_DIR = Path.cwd()
SRC_DIR = BASE_DIR / "gf" / "generated" / "src"

def fix_grammars():
    print(f"🧹 Scanning {SRC_DIR}...")
    
    patched_count = 0
    deleted_count = 0
    
    for file_path in SRC_DIR.glob("Wiki*.gf"):
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # --- PROBLEM 2: Check for Lazy "WikiI" usage ---
            # If the file contains "= WikiI", it depends on a missing file. Delete it.
            if "= WikiI" in content or "=WikiI" in content:
                print(f"🗑️  Deleting Lazy Grammar: {file_path.name}")
                file_path.unlink()
                deleted_count += 1
                continue # Skip patching if deleted

            # --- PROBLEM 1: Fix Module Name Mismatch ---
            # Filename: WikiChi.gf -> Expected Module: WikiChi
            expected_module = file_path.stem 
            
            # Regex: Find "concrete WikiSomething of"
            pattern = re.compile(r"concrete\s+(Wiki\w+)\s+of", re.IGNORECASE)
            match = pattern.search(content)
            
            if match:
                current_module = match.group(1)
                if current_module != expected_module:
                    print(f"🔧 Patching {file_path.name}: {current_module} -> {expected_module}")
                    new_content = content.replace(current_module, expected_module)
                    file_path.write_text(new_content, encoding="utf-8")
                    patched_count += 1
                    
        except Exception as e:
            print(f"❌ Error processing {file_path.name}: {e}")

    print("-" * 40)
    print(f"✅ Summary: Patched {patched_count} files (Identity Fix).")
    print(f"♻️  Summary: Deleted {deleted_count} files (Lazy AI Fix).")
    print("👉 Run 'python manage.py generate' to regenerate the deleted ones.")

if __name__ == "__main__":
    fix_grammars()