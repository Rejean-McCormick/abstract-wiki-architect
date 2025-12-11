import os
import json
import glob

# Path to the central configuration
CONFIG_PATH = 'config/everything_matrix_config.json'

def load_config():
    """Loads the central configuration."""
    if not os.path.exists(CONFIG_PATH):
        print(f"⚠️ Config not found at {CONFIG_PATH}, using defaults.")
        return {
            "frontend": {
                "profiles_path": "architect_frontend/src/config/language_profiles.json",
                "assets_path": "architect_frontend/public/flags"
            },
            # Fallback path for backend app logic (non-RGL)
            "backend_config_path": "data/morphology_configs" 
        }
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def scan_application():
    """
    Scans the Application layer (Frontend & Backend Configs).
    Returns a dictionary keyed by Wiki Code with scores for each block.
    """
    config = load_config()
    fe_config = config.get("frontend", {})
    
    profiles_path = fe_config.get("profiles_path", "architect_frontend/src/config/language_profiles.json")
    assets_path = fe_config.get("assets_path", "architect_frontend/public/flags")
    backend_path = config.get("backend_config_path", "data/morphology_configs")

    scores = {}

    print("🔍 Scanning Application Layer...")

    # 1. SCAN FRONTEND PROFILES
    # Checks if the language is registered in the UI configuration.
    if os.path.exists(profiles_path):
        try:
            with open(profiles_path, 'r') as f:
                profiles = json.load(f)
                
            # Assuming structure: { "eng": { "wiki_code": "Eng", "name": "English" }, ... }
            # Or list: [ { "iso": "en", "wiki_code": "Eng" } ... ]
            
            # We normalize to handle both dict and list structures
            profile_list = profiles.values() if isinstance(profiles, dict) else profiles
            
            for profile in profile_list:
                # We look for the 'wiki_code' field which links to our Matrix
                w_code = profile.get("wiki_code")
                if w_code and len(w_code) == 3:
                    if w_code not in scores: scores[w_code] = {}
                    scores[w_code]["app_profile"] = 10
                    
        except Exception as e:
            print(f"⚠️ Could not parse profiles at {profiles_path}: {e}")

    # 2. SCAN UI ASSETS (FLAGS)
    # Checks for existence of flag icons.
    # Heuristic: Checks for {wiki_code}.svg OR {iso_code}.svg if we can map it.
    if os.path.exists(assets_path):
        flag_files = glob.glob(os.path.join(assets_path, "*.svg"))
        for f in flag_files:
            filename = os.path.basename(f)
            code = filename.replace(".svg", "")
            
            # Case A: Filename is Wiki Code (e.g., "Eng.svg")
            if len(code) == 3 and code[0].isupper():
                if code not in scores: scores[code] = {}
                scores[code]["app_assets"] = 10
            
            # Case B: Filename is ISO (e.g., "en.svg") - Simple 2-letter detection
            # Note: A real implementation would need a distinct ISO map, 
            # but here we log it if we already found the profile for it.
            elif len(code) == 2:
                # We can't easily map 'en' -> 'Eng' without the map file,
                # so we assume if app_profile exists, the asset is likely correct.
                # This is a soft check.
                pass

    # 3. SCAN BACKEND ROUTES / CONFIG
    # Checks if the Python backend has specific logic config for this language.
    # (e.g., data/morphology_configs/romance.json or specific overrides)
    if os.path.exists(backend_path):
        # This is a proxy for "App Routes". If config exists, route is active.
        backend_files = glob.glob(os.path.join(backend_path, "*.json"))
        for f in backend_files:
            # Files might be named "romance.json" (family) or "fra.json" (iso) or "Fre.json" (wiki)
            filename = os.path.basename(f)
            code = filename.replace(".json", "")
            
            # If we find a config matching a Wiki code
            if len(code) == 3 and code[0].isupper():
                if code not in scores: scores[code] = {}
                scores[code]["app_routes"] = 10

    return scores

if __name__ == "__main__":
    # Standalone test
    results = scan_application()
    print(json.dumps(results, indent=2))
    print(f"✅ Scanned application layer for {len(results)} languages.")