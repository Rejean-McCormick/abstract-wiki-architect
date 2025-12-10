import os
import glob
import re

GF_DIR = "gf"

def run():
    print("🚀 Linking Dictionaries to Grammars (Verbose Mode)...")
    
    files = glob.glob(os.path.join(GF_DIR, "Wiki*.gf"))
    files += glob.glob(os.path.join(GF_DIR, "Wiki*.gf.SKIP"))

    count_linked = 0
    count_skipped = 0

    for file_path in files:
        filename = os.path.basename(file_path)
        # Skip Abstract and unrelated files
        if "Wiki.gf" in filename and len(filename) < 12: continue
        
        # Determine language code
        clean_name = filename.replace(".SKIP", "").replace("Wiki", "").replace(".gf", "")
        lang_code = clean_name
        
        # Read content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Regex to find the "open ... in" block
        pattern = r"(open\s+)(.*?)(\s+in)"
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            prefix = match.group(1)
            current_modules = match.group(2)
            suffix = match.group(3)
            
            print(f"\n🔍 Checking {filename}...")
            print(f"   Current imports: [{current_modules.strip()}]")

            added = []
            new_modules_str = current_modules

            # Check for Dictionary
            dict_mod = f"Dict{lang_code}"
            if dict_mod not in current_modules:
                new_modules_str += f", {dict_mod}"
                added.append(dict_mod)

            # Check for Symbolic
            symb_mod = f"Symbolic{lang_code}"
            if symb_mod not in current_modules:
                new_modules_str += f", {symb_mod}"
                added.append(symb_mod)

            # Check for Prelude (Critical for the robust forge)
            if "Prelude" not in current_modules:
                new_modules_str += ", Prelude"
                added.append("Prelude")

            if added:
                new_content = content.replace(current_modules, new_modules_str)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"   ✅ Linked: {', '.join(added)}")
                count_linked += 1
                
                # Restore if SKIP
                if file_path.endswith(".SKIP"):
                    restored = file_path.replace(".SKIP", "")
                    os.rename(file_path, restored)
                    print(f"   ✨ Restored to {os.path.basename(restored)}")
            else:
                print("   👌 Already linked.")
                count_skipped += 1
                
                # Restore anyway if it was skipped but correct
                if file_path.endswith(".SKIP"):
                    restored = file_path.replace(".SKIP", "")
                    os.rename(file_path, restored)
                    print(f"   ✨ Restored to {os.path.basename(restored)}")
        else:
            print(f"⚠️  WARNING: Could not parse imports in {filename}")

    print(f"\nSummary: {count_linked} files updated, {count_skipped} already correct.")

if __name__ == "__main__":
    run()