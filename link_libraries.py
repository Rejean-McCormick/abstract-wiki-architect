import os
import glob
import re

GF_DIR = "gf"

def run():
    print("🚀 Linking Dictionaries to Grammars...")
    
    # Get all Wiki files (including skipped ones)
    files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    files += glob.glob(os.path.join(GF_DIR, "Wiki*.gf.SKIP"))

    for file_path in files:
        if "Wiki.gf" in file_path and len(os.path.basename(file_path)) < 12: continue

        # Identify Language Code (WikiAfr -> Afr)
        filename = os.path.basename(file_path)
        clean_name = filename.replace(".SKIP", "").replace("Wiki", "").replace(".gf", "")
        lang_code = clean_name
        
        # Read content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Regex to find the "open ... in" line
        # We look for "open SyntaxAfr" or similar and append our modules
        pattern = r"(open\s+)(.*?)(\s+in)"
        
        def linker(match):
            prefix = match.group(1)   # "open "
            modules = match.group(2)  # "SyntaxAfr"
            suffix = match.group(3)   # " in"
            
            # Add Dict and Symbolic if not present
            new_modules = modules
            if f"Dict{lang_code}" not in new_modules:
                new_modules += f", Dict{lang_code}"
            if f"Symbolic{lang_code}" not in new_modules:
                new_modules += f", Symbolic{lang_code}"
            
            return f"{prefix}{new_modules}{suffix}"

        new_content = re.sub(pattern, linker, content)
        
        # Write back if changed
        if new_content != content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"   🔗 Linked {filename}")
            
            # If it was a SKIP file, restore it now because it should be fixed!
            if file_path.endswith(".SKIP"):
                restored_path = file_path.replace(".SKIP", "")
                os.rename(file_path, restored_path)
                print(f"      ✨ Restored {filename}")

if __name__ == "__main__":
    run()