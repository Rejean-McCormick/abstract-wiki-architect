import json
import logging
from pathlib import Path
import sys

# --- CONFIGURATION ---
ROOT_DIR = Path(__file__).parent.parent
CONFIG_DIR = ROOT_DIR / "data" / "config"
FACTORY_TARGETS_FILE = CONFIG_DIR / "factory_targets.json"
TOPOLOGY_WEIGHTS_FILE = CONFIG_DIR / "topology_weights.json"

# Setup Logging
logger = logging.getLogger("GrammarFactory")

# --- SHARED IMPORTS ---
sys.path.append(str(ROOT_DIR))
try:
    from app.shared.languages import ISO_2_TO_3
except ImportError:
    ISO_2_TO_3 = {}

# --- DEFAULTS ---
DEFAULT_WEIGHTS = {
    "SVO": {"nsubj": -10, "root": 0, "obj": 10, "iobj": 5},
    "SOV": {"nsubj": -10, "obj": -5, "iobj": -2, "root": 0},
    "VSO": {"root": -10, "nsubj": 0, "obj": 10, "iobj": 15},
    "VOS": {"root": -10, "obj": 5, "nsubj": 10},
    "OVS": {"obj": -10, "root": 0, "nsubj": 10},
    "OSV": {"obj": -10, "nsubj": -5, "root": 0}
}

def load_json_config(path, default=None):
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️  Failed to load config {path.name}: {e}")
    return default if default is not None else {}

def get_topology(iso3_code):
    targets = load_json_config(FACTORY_TARGETS_FILE)
    if iso3_code in targets:
        return targets[iso3_code].get("order", "SVO")
    
    static_overrides = {
        "jpn": "SOV", "hin": "SOV", "kor": "SOV", "tur": "SOV", 
        "urd": "SOV", "fas": "SOV", "ara": "VSO", "heb": "VSO"
    }
    return static_overrides.get(iso3_code, "SVO")

def _build_linearization(components, weights):
    # Sort by the weight of the role
    components.sort(key=lambda x: weights.get(x["role"], 0))
    # Join the GF code strings using '++'
    return " ++ ".join([item["code"] for item in components])

def generate_safe_mode_grammar(lang_code):
    """
    Generates a Safe Mode grammar.
    FIX 2.0: Treats 'String' inputs as already-wrapped SS records {s : Str}.
    """
    iso3 = ISO_2_TO_3.get(lang_code, lang_code).lower()
    order = get_topology(iso3)
    
    weights_db = load_json_config(TOPOLOGY_WEIGHTS_FILE, DEFAULT_WEIGHTS)
    weights = weights_db.get(order, weights_db["SVO"])
    
    # --- 1. Linearization Strategies ---
    
    # Note: We must access '.s' on the arguments because they are SS records
    # But the result of _build_linearization is a raw Str expression.
    # We will wrap the RESULT in 'ss(...)'.

    # mkBioProf: Entity (nsubj) + "is a" (root) + Prof (obj)
    bio_prof_lin = _build_linearization([
        {"code": "entity.s",   "role": "nsubj"},
        {"code": "\"is a\"",   "role": "root"},
        {"code": "prof.s",     "role": "obj"}
    ], weights)

    # mkBioNat: Entity (nsubj) + "is" (root) + Nat (obj)
    bio_nat_lin = _build_linearization([
        {"code": "entity.s",   "role": "nsubj"},
        {"code": "\"is\"",     "role": "root"},
        {"code": "nat.s",      "role": "obj"} 
    ], weights)

    # mkBioFull: Entity (nsubj) + "is a" (root) + Nat+Prof (obj)
    bio_full_lin = _build_linearization([
        {"code": "entity.s",      "role": "nsubj"},
        {"code": "\"is a\"",      "role": "root"},
        {"code": "nat.s ++ prof.s", "role": "obj"} 
    ], weights)

    # mkEvent: Entity (nsubj) + "participated in" (root) + Event (obj)
    event_lin = _build_linearization([
        {"code": "entity.s",            "role": "nsubj"},
        {"code": "\"participated in\"", "role": "root"},
        {"code": "event.s",             "role": "obj"}
    ], weights)

    # --- 2. Generate Code ---
    lang_name = f"Wiki{lang_code.title()}"
    
    # CRITICAL FIX IN 'lin': 
    # mkEntityStr s = s; (No 'ss' wrapper, because 's' is already SS)
    # mkBio... = ss (...); (Wrap the result string back into SS)

    gf_code = f"""concrete {lang_name} of AbstractWiki = open Prelude in {{
  lincat
    Statement = SS;
    Entity = SS;
    Profession = SS;
    Nationality = SS;
    EventObj = SS;

  lin
    -- Dynamic Topology: {iso3} ({order})

    -- 1. Wrappers (Pass-through because input is already SS)
    mkEntityStr s = s;
    strProf s = s;
    strNat s = s;
    strEvent s = s;
    
    -- 2. Bio Frames (Wrap the constructed string)
    mkBioProf entity prof = ss ({bio_prof_lin});
    mkBioNat entity nat = ss ({bio_nat_lin});
    mkBioFull entity prof nat = ss ({bio_full_lin});

    -- 3. Event Frames
    mkEvent entity event = ss ({event_lin});

}}
"""
    return gf_code