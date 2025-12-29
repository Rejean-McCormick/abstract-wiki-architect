import os
import json
import time
import logging
import sys
import hashlib
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

# Asset Paths
LEXICON_DIR = BASE_DIR / "data" / "lexicon"
RGL_SRC = BASE_DIR / "gf-rgl" / "src"
FACTORY_SRC = BASE_DIR / "gf" / "generated" / "src"
GF_ARTIFACTS = BASE_DIR / "gf"

# Add current dir to path to import sibling scanners
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import Scanners
try:
    import rgl_auditor
except ImportError:
    rgl_auditor = None

try:
    import lexicon_scanner
except ImportError:
    lexicon_scanner = None

try:
    import qa_scanner
except ImportError:
    qa_scanner = None

# --- THE ROSETTA STONE ---
# Critical Mapping: ISO 639-3 (RGL/Factory) -> ISO 639-1 (System)
ISO_3_TO_2 = {
    # Tier 1 (RGL)
    "eng": "en", "fra": "fr", "deu": "de", "spa": "es", "ita": "it", 
    "swe": "sv", "por": "pt", "rus": "ru", "zho": "zh", "jpn": "ja", 
    "ara": "ar", "hin": "hi", "fin": "fi", "est": "et", "swa": "sw", 
    "tur": "tr", "bul": "bg", "pol": "pl", "ron": "ro", "nld": "nl", 
    "dan": "da", "nob": "no", "isl": "is", "ell": "el", "heb": "he", 
    "lav": "lv", "lit": "lt", "mlt": "mt", "hun": "hu", "cat": "ca", 
    "eus": "eu", "tha": "th", "urd": "ur", "fas": "fa", "mon": "mn", 
    "nep": "ne", "pan": "pa", "snd": "sd", "afr": "af", "amh": "am", 
    "kor": "ko", "lat": "la", "nno": "nn", "slv": "sl", "som": "so", 
    "tgl": "tl", "vie": "vi", "pes": "fa", "pnb": "pa", "hrv": "hr",
    "cze": "cs", "dut": "nl", "ger": "de", "gre": "el", "ice": "is",
    "ina": "ia", "may": "ms", "slo": "sk", "hye": "hy", "bel": "be",
    "fao": "fo", "gla": "gd", "kaz": "kk", "mkd": "mk", "tel": "te",
    "ukr": "uk", "zul": "zu", 
    
    # Tier 3 (Factory Targets)
    "xho": "xh", "yor": "yo", "ibo": "ig", "hau": "ha", "wol": "wo",
    "kin": "rw", "lug": "lg", "lin": "ln", "ind": "id", "msa": "ms",
    "jav": "jv", "tam": "ta", "ben": "bn", "uzb": "uz", "que": "qu",
    "aym": "ay", "nav": "nv", "grn": "gn", "fry": "fy", "bre": "br",
    "oci": "oc", "cym": "cy", "tat": "tt", "kur": "ku"
}

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
                    iso2 = ISO_3_TO_2.get(iso3)
                    
                    if iso2:
                        raw_path = info.get("path")
                        
                        # --- SMART FIX: Redirect 'api' paths to real source ---
                        # Some languages (Ara, Cat, Bul) point to 'api' by default.
                        # We must find their real home by looking at their modules.
                        if raw_path and raw_path.endswith("api"):
                            modules = info.get("modules", {})
                            
                            # Try 'Cat' first, then 'Grammar', then 'Noun'
                            # This fixes cases like Catalan which lack 'Cat' but have 'Grammar'
                            ref_file = modules.get("Cat") or modules.get("Grammar") or modules.get("Noun")
                            
                            if ref_file:
                                # Extract folder: "gf-rgl/src/catalan/GrammarCat.gf" -> "gf-rgl/src/catalan"
                                raw_path = str(Path(ref_file).parent)

                        rgl_map[iso2] = {
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
                    iso2 = ISO_3_TO_2.get(iso3)
                    if iso2:
                        factory_map[iso2] = info
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
    # ---------------------------------------------------------
    # 0. Caching Logic
    # ---------------------------------------------------------
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_fingerprint = get_directory_fingerprint([RGL_SRC, LEXICON_DIR, FACTORY_SRC])
    
    if CHECKSUM_FILE.exists() and MATRIX_FILE.exists():
        with open(CHECKSUM_FILE, 'r') as f:
            stored_fingerprint = f.read().strip()
        if current_fingerprint == stored_fingerprint:
            logger.info("⚡ Cache Hit: Filesystem unchanged. Skipping scan.")
            return

    logger.info("🧠 Everything Matrix v2.1: Deep System Scan Initiated...")
    
    # Load Reference Data
    rgl_registry, factory_registry = load_central_registries()
    
    matrix_langs = {}
    all_isos = set()

    # ---------------------------------------------------------
    # 1. DISCOVERY PHASE (Normalize everything to ISO-2)
    # ---------------------------------------------------------
    all_isos.update(rgl_registry.keys())
    all_isos.update(factory_registry.keys())
    
    if FACTORY_SRC.exists():
        for p in FACTORY_SRC.iterdir():
            if p.is_dir():
                iso_norm = ISO_3_TO_2.get(p.name, p.name)
                all_isos.add(iso_norm)
    
    if LEXICON_DIR.exists():
        for p in LEXICON_DIR.iterdir():
            if p.is_dir():
                iso_norm = ISO_3_TO_2.get(p.name, p.name)
                all_isos.add(iso_norm)

    # ---------------------------------------------------------
    # 2. SCAN LOOP
    # ---------------------------------------------------------
    for iso in sorted(all_isos):
        # --- Zone A: RGL Engine (Logic) ---
        zone_a = {"CAT": 0, "NOUN": 0, "PARA": 0, "GRAM": 0, "SYN": 0}
        tier = 3
        origin = "factory"
        rgl_folder = "generated"
        
        # Check if it's in the RGL Registry (Tier 1)
        if iso in rgl_registry:
            entry = rgl_registry[iso]
            full_path = BASE_DIR / entry["path"]
            
            if full_path.exists():
                tier = 1
                origin = "rgl"
                rgl_folder = Path(entry["path"]).name
                
                # Run Auditor
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

        matrix_langs[iso] = {
            "meta": {
                "iso": iso,
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