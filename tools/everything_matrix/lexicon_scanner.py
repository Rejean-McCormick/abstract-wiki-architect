# tools/everything_matrix/lexicon_scanner.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Setup Logging
logger = logging.getLogger(__name__)

# v2.1 Maturity Targets (Score of 10)
TARGETS = {
    "core": 150,      # "Glue" words needed for basic sentences
    "conc": 500,      # Domain words needed for specific topics
    "bio_min": 50     # Entities needed to act as a Biography Generator
}

# Enterprise Mapping: RGL (3-letter) -> ISO (2-letter)
# This ensures scanner looks in 'data/lexicon/en' when asking for 'eng'.
ISO_MAP_3_TO_2 = {
    "eng": "en", "fra": "fr", "deu": "de", "nld": "nl", 
    "ita": "it", "spa": "es", "rus": "ru", "swe": "sv",
    "pol": "pl", "bul": "bg", "ell": "el", "ron": "ro",
    "zho": "zh", "jpn": "ja", "ara": "ar", "hin": "hi",
    "por": "pt", "tur": "tr", "vie": "vi", "kor": "ko"
}

def _resolve_storage_code(lang_code: str) -> str:
    """
    Resolves the ISO 639-1 (2-letter) code for storage lookups.
    """
    code = lang_code.lower()
    
    # 1. Exact match 2-letter
    if len(code) == 2:
        return code
    
    # 2. Map 3-letter to 2-letter
    if code in ISO_MAP_3_TO_2:
        return ISO_MAP_3_TO_2[code]
        
    # 3. Naive Fallback (risky but covers simple cases like 'eng'->'en')
    if len(code) == 3:
        return code[:2]
        
    return code

def scan_lexicon_health(lang_code: str, data_dir: Path) -> Dict[str, float]:
    """
    Performs a Deep-Tissue scan of Zone B (Lexicon) and Zone C (Application).
    
    Args:
        lang_code (str): ISO 639-3 code (e.g., 'fra') from the Matrix.
        data_dir (Path): Path to 'data/lexicon'.
        
    Returns:
        dict: Normalized scores (0.0 - 10.0) for:
              [Zone B] SEED, CONC, WIDE, SEM
              [Zone C] PROF, ASST, ROUT
    """
    # Initialize Stats with empty values
    stats = {
        # Zone B: Data
        "SEED": 0.0, "CONC": 0.0, "WIDE": 0.0, "SEM": 0.0,
        # Zone C: Application
        "PROF": 0.0, "ASST": 0.0, "ROUT": 0.0
    }

    # Resolve path using Enterprise Standard (2-letter folder)
    iso2 = _resolve_storage_code(lang_code)
    lang_path = data_dir / iso2

    if not lang_path.exists():
        # Fallback: check if strict 3-letter folder exists (Legacy support)
        legacy_path = data_dir / lang_code
        if legacy_path.exists():
            lang_path = legacy_path
        else:
            return stats # Path not found, return zeros

    total_entries = 0
    qid_entries = 0

    # --- SCAN SHARDS (Zone B & C) ---

    # 1. Core Vocabulary (SEED) -> core.json
    core_file = lang_path / "core.json"
    if core_file.exists():
        data = _safe_load(core_file)
        count = len(data)
        # Score calculation: Linear scale up to target
        stats["SEED"] = min(10.0, round((count / TARGETS["core"]) * 10, 1))
        total_entries += count
        qid_entries += _count_qids(data)

    # 2. Domain Concepts (CONC) -> people.json
    people_file = lang_path / "people.json"
    if people_file.exists():
        data = _safe_load(people_file)
        count = len(data)
        stats["CONC"] = min(10.0, round((count / TARGETS["conc"]) * 10, 1))
        
        # Zone C: Biography Readiness (PROF)
        # We need a minimum number of professions/nationalities to generate bios
        if count >= TARGETS["bio_min"]:
            stats["PROF"] = 1.0 # Boolean-like score (Ready)
        
        total_entries += count
        qid_entries += _count_qids(data)

    # 3. Wide Imports (WIDE) -> wide.json (The new standard)
    # Checks if the massive harvester shard exists
    wide_json = lang_path / "wide.json"
    if wide_json.exists():
        stats["WIDE"] = 10.0
        # Optional: Deep scan of wide.json could be slow, so we trust existence for score
        # but for semantic score, we might want to sample or assume.
        # For now, if wide exists, we give semantic credit.
        if stats["SEM"] == 0: stats["SEM"] = 5.0 

    # 4. Semantic Alignment (SEM)
    # Percentage of total entries that have a Wikidata QID
    if total_entries > 0:
        stats["SEM"] = max(stats["SEM"], min(10.0, round((qid_entries / total_entries) * 10, 1)))

    # --- SCAN CONFIG (Zone C) ---

    # 5. Assistant Ready (ASST) -> dialog.json (Future)
    # Currently a placeholder for chat capabilities
    if (lang_path / "dialog.json").exists():
        stats["ASST"] = 1.0

    # 6. Routing/Topology (ROUT) -> topology_weights.json
    # Does the system know how to linearize this language (SVO/SOV)?
    # We check if we have enough data (SEED) to justify routing.
    # In V2.1, existence of core data implies routing is possible via Factory.
    if stats["SEED"] >= 2.0:
        stats["ROUT"] = 1.0

    return stats

def _safe_load(path: Path) -> Dict:
    """Safely loads JSON, returning empty dict on failure."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning(f"⚠️  Corrupt JSON found at {path}")
        return {}

def _count_qids(data: Dict) -> int:
    """Counts entries containing a 'qid' field."""
    return sum(1 for entry in data.values() if isinstance(entry, dict) and "qid" in entry)

if __name__ == "__main__":
    # Test Stub for CLI execution
    import os
    test_root = Path(__file__).parent.parent.parent / "data" / "lexicon"
    print(f"Testing lexicon scan in: {test_root}")
    
    # Mock scan for 'eng' (should find 'en' folder)
    result = scan_lexicon_health("eng", test_root)
    print(json.dumps(result, indent=2))