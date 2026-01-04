import json
from pathlib import Path

# Paths
BASE_DIR = Path.cwd()
CONFIG_FILE = BASE_DIR / "data" / "config" / "everything_matrix_config.json"

def fix_config():
    print(f"📂 Reading config: {CONFIG_FILE}")
    
    if not CONFIG_FILE.exists():
        print("❌ Config file not found!")
        return

    try:
        data = json.loads(CONFIG_FILE.read_text())
        
        # 1. Check/Fix High Road Threshold
        matrix_cfg = data.get("matrix", {})
        high_road = matrix_cfg.get("high_road", {})
        current_val = high_road.get("min_maturity")
        
        print(f"🧐 Current 'min_maturity' setting: {current_val}")
        
        if current_val != 4.0:
            print("⚠️  DETECTED BLOCKER: Config is overriding code default.")
            print("🛠️  Patching config to 4.0...")
            
            # Ensure structure exists
            if "matrix" not in data: data["matrix"] = {}
            if "high_road" not in data["matrix"]: data["matrix"]["high_road"] = {}
            
            # Apply fix
            data["matrix"]["high_road"]["min_maturity"] = 4.0
            
            # Save
            CONFIG_FILE.write_text(json.dumps(data, indent=2))
            print("✅ Config updated successfully.")
        else:
            print("✅ Config is already correct (4.0).")

        # 2. Check Inventory Path
        rgl_cfg = data.get("rgl", {})
        inv_path = rgl_cfg.get("inventory_file", "data/indices/rgl_inventory.json")
        print(f"\n📂 RGL Inventory Path in Config: '{inv_path}'")
        
        real_path = BASE_DIR / inv_path
        if real_path.exists():
            print(f"   - File exists at: {real_path}")
            # Check timestamp of that file
            content = json.loads(real_path.read_text())
            ts = content.get("meta", {}).get("generated_at_iso", "UNKNOWN")
            print(f"   - Timestamp in file: {ts}")
        else:
            print(f"❌ File does not exist at configured path!")

    except Exception as e:
        print(f"❌ Error processing config: {e}")

if __name__ == "__main__":
    fix_config()