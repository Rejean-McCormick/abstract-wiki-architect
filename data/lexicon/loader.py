"""
data/lexicon/loader.py
======================
Runtime loader for the new Domain-Sharded Lexicon architecture.
Loads, merges, and normalizes lexicon files from data/lexicon/{lang}/.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Mapping, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base path: data/lexicon/
BASE_DIR = Path(__file__).resolve().parent

def _load_json_file(path: Path) -> Dict[str, Any]:
    """Helper to safely load a JSON file."""
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Error loading {path.name}: {e}")
        return {}

def _normalize_entry(base_key: str, entry: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Expands a single entry into a lookup map of surface forms.
    """
    normalized_map: Dict[str, Dict[str, Any]] = {}

    # Extract base features
    base_features = {
        "pos": entry.get("pos"),
        "gender": entry.get("gender"),
        "human": entry.get("human", entry.get("semantic_class") == "profession"),
        "nationality": entry.get("nationality", entry.get("semantic_class") in ["demonym", "nationality"]),
        "qid": entry.get("qid") or entry.get("wikidata_qid"),
        "lemma": entry.get("lemma") or base_key
    }

    # 1. Index the base lemma
    normalized_map[str(base_features["lemma"])] = dict(base_features)

    # 2. Index all surface forms from the "forms" map
    forms = entry.get("forms")
    if isinstance(forms, Mapping):
        for tag, surface in forms.items():
            if not isinstance(surface, str): continue

            # Clone features for the inflected form
            feat = dict(base_features)
            
            # Parse tag (e.g. "f.sg", "m.pl") to refine features
            if isinstance(tag, str):
                parts = tag.split(".")
                g_tag = parts[0] if len(parts) > 0 else None
                n_tag = parts[1] if len(parts) > 1 else None

                if g_tag in {"m", "f", "n", "neut", "common"}:
                    feat["gender"] = g_tag
                if n_tag in {"sg", "pl"}:
                    feat["number"] = n_tag

            normalized_map[surface] = feat

    return normalized_map

def available_languages() -> List[str]:
    """
    Return a sorted list of language codes for which a lexicon directory exists.
    """
    if not BASE_DIR.is_dir():
        return []

    langs = []
    # Scan for directories that are not hidden/special (start with _)
    for item in BASE_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("-"):
            # Check if it looks like a lang folder (contains JSONs)
            if any(item.glob("*.json")):
                langs.append(item.name)
    
    # Fallback: check for legacy root .json files
    for item in BASE_DIR.glob("*_lexicon.json"):
        code = item.name.replace("_lexicon.json", "")
        if code not in langs:
            langs.append(code)

    return sorted(langs)

def load_lexicon(lang_code: str) -> Dict[str, Any]:
    """
    Load and merge all lexicon files for a given language code.
    
    Returns:
        Dict: A flattened dictionary of {surface_form: features}.
              (NOT wrapped in "entries" key).
    """
    lang_dir = BASE_DIR / lang_code
    
    merged_entries: Dict[str, Dict[str, Any]] = {}
    
    # Helper to extract data from raw JSON
    def process_data(raw_data):
        sources = []
        if "entries" in raw_data: sources.append(raw_data["entries"])
        if "lemmas" in raw_data: sources.append(raw_data["lemmas"])
        for cat in ["professions", "titles", "nationalities", "honours"]:
            if cat in raw_data: sources.append(raw_data[cat])
            
        for source_dict in sources:
            if isinstance(source_dict, Mapping):
                for key, entry in source_dict.items():
                    if isinstance(entry, Mapping):
                        merged_entries.update(_normalize_entry(key, entry))

    # 1. Try loading from the new folder structure
    if lang_dir.is_dir():
        files = sorted(lang_dir.glob("*.json"))
        if not files:
            logger.warning(f"Lexicon folder for '{lang_code}' exists but is empty.")
        
        for file_path in files:
            raw_data = _load_json_file(file_path)
            if raw_data: process_data(raw_data)

    # 2. Fallback: Try the old single-file location
    else:
        legacy_file = BASE_DIR / f"{lang_code}_lexicon.json"
        if legacy_file.exists():
            logger.info(f"Loading legacy file: {legacy_file.name}")
            raw_data = _load_json_file(legacy_file)
            if raw_data: process_data(raw_data)
        else:
            logger.error(f"No lexicon found for language: {lang_code}")

    logger.info(f"Loaded {len(merged_entries)} surface forms for '{lang_code}'.")
    
    # CRITICAL FIX: Return the dictionary directly.
    # The engine expects {"physicien": {...}}, not {"entries": {"physicien": ...}}
    return merged_entries

__all__ = [
    "load_lexicon",
    "available_languages",
]

if __name__ == "__main__":
    import sys
    print(f"Available languages: {available_languages()}")
    if len(sys.argv) > 1:
        test_lang = sys.argv[1]
        lex = load_lexicon(test_lang)
        # Note: 'lex' is now the direct dictionary, so we check len(lex), not len(lex['entries'])
        print(f"Loaded {len(lex)} entries for {test_lang}")