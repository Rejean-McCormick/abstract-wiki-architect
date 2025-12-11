import os
import shutil

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
TARGET_DIR = "gf"
# Files we want to KEEP but move to the gf/ folder
MOVE_EXTENSIONS = [".gf"]
# Files we want to DELETE (compiler artifacts)
DELETE_EXTENSIONS = [".gfo"]

def run():
    print(f"🧹 Cleaning Root Directory... (Target: {TARGET_DIR}/)")
    
    # Ensure target directory exists
    if not os.path.exists(TARGET_DIR):
        os.makedirs(TARGET_DIR)
        print(f"   Created directory: {TARGET_DIR}")

    # Scan the current directory (Root)
    files = [f for f in os.listdir(".") if os.path.isfile(f)]
    
    moved_count = 0
    deleted_count = 0

    for filename in files:
        # Skip this script itself
        if filename == os.path.basename(__file__):
            continue
            
        name, ext = os.path.splitext(filename)
        
        # 1. Move Source Files (.gf)
        if ext in MOVE_EXTENSIONS and filename.startswith("Wiki"):
            src = filename
            dst = os.path.join(TARGET_DIR, filename)
            
            # Prevent overwriting if file already exists in gf/ (Safety check)
            if os.path.exists(dst):
                print(f"   ⚠️  Duplicate found in {TARGET_DIR}/: {filename}. (Skipping move)")
            else:
                shutil.move(src, dst)
                print(f"   📦 Moved: {filename} -> {TARGET_DIR}/")
                moved_count += 1
                
        # 2. Delete Artifacts (.gfo)
        elif ext in DELETE_EXTENSIONS and filename.startswith("Wiki"):
            os.remove(filename)
            print(f"   🔥 Deleted: {filename}")
            deleted_count += 1

    print("-" * 40)
    print(f"Cleanup Complete.")
    print(f"   Moved:   {moved_count} source files")
    print(f"   Deleted: {deleted_count} junk files")

if __name__ == "__main__":
    run()