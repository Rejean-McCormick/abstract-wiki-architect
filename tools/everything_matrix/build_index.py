import os
import json
import time
import logging
import sys
import hashlib
import argparse
from pathlib import Path

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data" / "indices"
CONFIG_DIR = BASE_DIR / "data" / "config"

# Central Registry Files
MATRIX_FILE = DATA_DIR / "everything_matrix.json"
CHECKSUM_FILE = DATA_DIR / "filesystem.checksum"
RGL_INVENTORY_FILE = DATA_DIR / "rgl_inventory.json"
FACTORY_TARGETS_FILE = CONFIG_DIR / "factory_targets.json"
ISO_MAP_FILE = BASE_DIR / "config" / "iso_to_wiki.json"

# Asset Paths
LEXICON_DIR = BASE_DIR / "data" / "lexicon"
RGL_SRC = BASE_DIR / "gf-rgl" / "src"
FACTORY_SRC = BASE_DIR / "gf" / "generated" / "src"
GF_ARTIFACTS = BASE_DIR / "gf"

# Add current dir to path to import sibling scanners
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- Import Scanners ---
try:
    import rgl_scanner as rgl_auditor 
except ImportError:
    logger.warning("⚠️ Could not import rgl_scanner. Zone A will be empty.")
    rgl_auditor = None

try:
    import lexicon_scanner
except ImportError:
    lexicon_scanner = None

try:
    import qa_scanner
except ImportError:
    qa_scanner = None

# --- DYNAMIC MAPPING LOADER ---
def load_iso_map():
    """
    Loads the authoritative ISO codes from config/iso_to_wiki.json.
    Returns a normalization map (iso_lower -> iso_canonical).
    """
    if not ISO_MAP_FILE.exists():
        logger.error(f"❌ ISO Map not found at {ISO_MAP_FILE}")
        return {}

    try:
        with open(ISO_MAP_FILE, 'r') as f:
            raw_map = json.load(f)
        
        mapping = {}
        # Build mapping: Normalize keys to lowercase for robust lookups
        for iso_code in raw_map.keys():
            iso_lower = iso_code.lower()
            mapping[iso_lower] = iso_lower
            
        return mapping

    except Exception as e:
        logger.error(f"❌ Failed to load ISO Map: {e}")
        return {}

# Load the map dynamically
ISO_NORM_MAP = load_iso_map()

def load_language_names():
    """
    Loads official language names from config/iso_to_wiki.json.
    Now supports the v2.0 object format: {"eng": {"wiki": "Eng", "name": "English"}}
    """
    if not ISO_MAP_FILE.exists():
        logger.warning(f"⚠️ ISO config not found at {ISO_MAP_FILE}")
        return {}
    
    try:
        with open(ISO_MAP_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        name_map = {}
        for code, info in data.items():
            # Handle v2.0 object format
            if isinstance(info, dict):
                name = info.get("name")
                if name:
                    name_map[code.lower()] = name
            # v1.0 string format (just code->suffix) has no name data, ignore
            
        return name_map
    except Exception as e:
        logger.error(f"❌ Failed to load language names: {e}")
        return {}

def load_central_registries():
    """
    Loads the JSON files that define the language universe.
    Implements ROBUST SMART FIX for 'api' paths.
    """
    rgl_map = {}
    factory_map = {}

    # 1. Load RGL Inventory (Tier 1)
    if RGL_INVENTORY_FILE.exists():
        try:
            with open(RGL_INVENTORY_FILE, 'r') as f:
                data = json.load(f)
                langs = data.get("languages", {})
                for rgl_code, info in langs.items():
                    iso3 = rgl_code.lower()
                    # Normalize using our map, or default to self
                    iso_norm = ISO_NORM_MAP.get(iso3, iso3)
                    
                    raw_path = info.get("path")
                    
                    if raw_path and raw_path.endswith("api"):
                        modules = info.get("modules", {})
                        ref_file = modules.get("Cat") or modules.get("Grammar") or modules.get("Noun")
                        if ref_file:
                            raw_path = str(Path(ref_file).parent)

                    rgl_map[iso_norm] = {
                        "path": raw_path, 
                        "rgl_code": rgl_code
                    }
        except Exception as e:
            logger.error(f"❌ Failed to load RGL Inventory: {e}")

    # 2. Load Factory Targets (Tier 3)
    if FACTORY_TARGETS_FILE.exists():
        try:
            with open(FACTORY_TARGETS_FILE, 'r') as f:
                data = json.load(f)
                for iso3, info in data.items():
                    iso_norm = ISO_NORM_MAP.get(iso3.lower(), iso3.lower())
                    factory_map[iso_norm] = info
        except Exception as e:
            logger.error(f"❌ Failed to load Factory Targets: {e}")
            
    return rgl_map, factory_map

def get_directory_fingerprint(paths):
    hasher = hashlib.md5()
    for path in paths:
        path = Path(path)
        if not path.exists(): continue
        for root, dirs, files in os.walk(path):
            for name in sorted(files):
                filepath = Path(root) / name
                try:
                    mtime = filepath.stat().st_mtime
                    raw = f"{name}|{mtime}"
                    hasher.update(raw.encode('utf-8'))
                except OSError: continue
    return hasher.hexdigest()

def scan_system():
    parser = argparse.ArgumentParser(description="Rebuilds the Everything Matrix index.")
    parser.add_argument("--force", action="store_true", help="Ignore cache and force full rebuild")
    args, _ = parser.parse_known_args()

    # ---------------------------------------------------------
    # 0. Caching Logic
    # ---------------------------------------------------------
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_fingerprint = get_directory_fingerprint([RGL_SRC, LEXICON_DIR, FACTORY_SRC])
    
    if not args.force and CHECKSUM_FILE.exists() and MATRIX_FILE.exists():
        with open(CHECKSUM_FILE, 'r') as f:
            stored_fingerprint = f.read().strip()
        if current_fingerprint == stored_fingerprint:
            logger.info("⚡ Cache Hit: Filesystem unchanged. Skipping scan.")
            logger.info("   (Run with --force to rebuild anyway)")
            return

    logger.info("🧠 Everything Matrix v2.1: Deep System Scan Initiated...")
    
    rgl_registry, factory_registry = load_central_registries()
    name_map = load_language_names()
    
    matrix_langs = {}
    all_isos = set()

    # ---------------------------------------------------------
    # 1. DISCOVERY PHASE (Normalize everything to System ISO)
    # ---------------------------------------------------------
    all_isos.update(rgl_registry.keys())
    all_isos.update(factory_registry.keys())
    
    if FACTORY_SRC.exists():
        for p in FACTORY_SRC.iterdir():
            if p.is_dir():
                norm = ISO_NORM_MAP.get(p.name.lower(), p.name.lower())
                all_isos.add(norm)
    
    if LEXICON_DIR.exists():
        for p in LEXICON_DIR.iterdir():
            if p.is_dir():
                norm = ISO_NORM_MAP.get(p.name.lower(), p.name.lower())
                all_isos.add(norm)

    # ---------------------------------------------------------
    # 2. SCAN LOOP
    # ---------------------------------------------------------
    for iso in sorted(all_isos):
        if iso == "api": continue

        # --- Zone A: RGL Engine (Logic) ---
        zone_a = {"CAT": 0, "NOUN": 0, "PARA": 0, "GRAM": 0, "SYN": 0}
        tier = 3
        origin = "factory"
        rgl_folder = "generated"
        
        if iso in rgl_registry:
            entry = rgl_registry[iso]
            full_path = BASE_DIR / entry["path"]
            
            if full_path.exists():
                tier = 1
                origin = "rgl"
                rgl_folder = Path(entry["path"]).name
                
                if rgl_auditor:
                    if hasattr(rgl_auditor, 'scan_rgl'):
                        zone_a = rgl_auditor.scan_rgl(iso, full_path)
                    elif hasattr(rgl_auditor, 'audit_language'):
                        audit = rgl_auditor.audit_language(iso, full_path)
                        zone_a = audit.get("blocks", zone_a)

        # --- Zone B & C: Lexicon & App (Data) ---
        zone_b = {"SEED": 0.0, "CONC": 0.0, "WIDE": 0.0, "SEM": 0.0}
        zone_c = {"PROF": 0.0, "ASST": 0.0, "ROUT": 0.0}
        
        if lexicon_scanner:
            lex_stats = lexicon_scanner.scan_lexicon_health(iso, LEXICON_DIR)
            zone_b = {k: lex_stats.get(k, 0.0) for k in zone_b}
            zone_c = {k: lex_stats.get(k, 0.0) for k in zone_c}

        # --- Zone D: QA ---
        zone_d = {"BIN": 0.0, "TEST": 0.0}
        if qa_scanner:
            zone_d = qa_scanner.scan_artifacts(iso, GF_ARTIFACTS)

        # ---------------------------------------------------------
        # 3. VERDICT
        # ---------------------------------------------------------
        score_a = sum(zone_a.values()) / 5 if zone_a else 0
        score_b = (zone_b["SEED"] + zone_b["CONC"] + zone_b["SEM"]) / 3
        maturity = round((score_a * 0.6) + (score_b * 0.4), 1)

        build_strategy = "SKIP"
        cat_score = zone_a.get("CAT", 0) or zone_a.get("rgl_cat", 0)
        
        if maturity > 7.0 and cat_score == 10:
            build_strategy = "HIGH_ROAD"
        elif iso in factory_registry:
            build_strategy = "SAFE_MODE"
        elif maturity > 2.0:
            build_strategy = "SAFE_MODE"

        runnable = zone_b["SEED"] >= 2.0 or build_strategy == "HIGH_ROAD"

        # --- Inject Name from Central Config ---
        display_name = name_map.get(iso, iso.upper()) 

        matrix_langs[iso] = {
            "meta": {
                "iso": iso,
                "name": display_name,
                "tier": tier,
                "origin": origin,
                "folder": rgl_folder
            },
            "zones": {
                "A_RGL": zone_a,
                "B_LEX": zone_b,
                "C_APP": zone_c,
                "D_QA": zone_d
            },
            "verdict": {
                "maturity_score": maturity,
                "build_strategy": build_strategy,
                "runnable": runnable
            }
        }

    # ---------------------------------------------------------
    # 4. SAVE
    # ---------------------------------------------------------
    matrix = {
        "timestamp": time.time(),
        "stats": {
            "total_languages": len(matrix_langs),
            "production_ready": sum(1 for l in matrix_langs.values() if l["verdict"]["maturity_score"] >= 8),
            "safe_mode": sum(1 for l in matrix_langs.values() if l["verdict"]["build_strategy"] == "SAFE_MODE"),
            "skipped": sum(1 for l in matrix_langs.values() if l["verdict"]["build_strategy"] == "SKIP"),
        },
        "languages": matrix_langs
    }

    with open(MATRIX_FILE, 'w') as f:
        json.dump(matrix, f, indent=2)
    
    with open(CHECKSUM_FILE, 'w') as f:
        f.write(current_fingerprint)
    
    logger.info(f"✅ Matrix Updated: {len(matrix_langs)} languages indexed.")

if __name__ == "__main__":
    scan_system()