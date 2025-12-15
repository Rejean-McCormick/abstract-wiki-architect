# lexicon\loader.py
"""
lexicon/loader.py
=================

Helpers to load and normalize per-language lexicon files from domain-sharded folders.

Goals
-----
- Provide a single entry point to load lexicon data from data/lexicon/{lang}/.
- Merge multiple domain files (core.json, people.json, science.json, etc.) into a single runtime dictionary.
- Hide filesystem details behind `lexicon.config`.
- Normalize schema differences (handling V2 "entries" vs legacy "lemmas").
- For callers, expose a flattened mapping:

    load_lexicon(lang_code) -> Dict[str, Dict[str, Any]]

  where keys are lemma / surface strings (e.g. "physicienne", "polonais") 
  and values are feature bundles (POS, gender, semantic class, etc.).

Current expectations
--------------------
- Lexica live under a directory configured via `lexicon.config`.
- Structure:
    data/lexicon/
      fr/
        core.json
        people.json
        ...
      en/
        ...

- Files are JSON dictionaries. Expected pattern (Schema V2):
    {
      "_meta": {...},
      "entries": {
        "physicien": {
          "pos": "NOUN",
          "forms": { "f.sg": "physicienne", ... }
        }
      }
    }

Error behaviour
---------------
- If the directory for a language does not exist, `load_lexicon(lang)`
  raises `FileNotFoundError`.
- Individual corrupt JSON files log a warning but do not crash the whole load
  (unless the directory is empty/invalid).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from lexicon.config import get_config

# Initialize logger
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """Infer the project root as the parent of this package directory."""
    return Path(__file__).resolve().parent.parent

def _lexicon_base_dir() -> Path:
    """
    Resolve the root directory where lexicon folders live.
    Uses `lexicon.config.get_config()`.
    """
    cfg = get_config()
    lex_dir = Path(cfg.lexicon_dir)
    if not lex_dir.is_absolute():
        lex_dir = _project_root() / lex_dir
    return lex_dir

def _language_dir(lang_code: str) -> Path:
    """
    Compute the path to the directory for a given language code.
    e.g., "fr" -> <lexicon_base>/fr/
    """
    return _lexicon_base_dir() / lang_code

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json_file(path: Path) -> Dict[str, Any]:
    """
    Load a single JSON file. Returns empty dict on failure (logs warning).
    """
    if not path.is_file():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(f"Skipping {path.name}: Root must be a dictionary.")
                return {}
            return data
    except json.JSONDecodeError as e:
        logger.warning(f"Skipping {path.name}: JSON decode error: {e}")
        return {}

def _normalize_entry(base_key: str, entry: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Convert a single raw entry into a dictionary of surface_form -> features.
    
    This handles the expansion of 'forms'. 
    Example Input:
        base_key="physicien", entry={"pos": "NOUN", "forms": {"f.sg": "physicienne"}}
    
    Example Output:
        {
            "physicien": {"pos": "NOUN", "gender": "m", ...},
            "physicienne": {"pos": "NOUN", "gender": "f", ...}
        }
    """
    normalized_map: Dict[str, Dict[str, Any]] = {}

    pos = entry.get("pos")
    gender = entry.get("gender")
    semantic_class = entry.get("semantic_class") or entry.get("category") # Support legacy key
    nationality_flag = entry.get("nationality")

    # Profession -> human = True (unless specified)
    human_flag: Optional[bool]
    if isinstance(entry.get("human"), bool):
        human_flag = entry.get("human")
    elif semantic_class == "profession":
        human_flag = True
    else:
        human_flag = None

    # Nationality / demonym -> nationality = True
    if isinstance(nationality_flag, bool):
        nat_flag: Optional[bool] = nationality_flag
    elif semantic_class in ("demonym", "nationality"):
        nat_flag = True
    else:
        nat_flag = None

    base_features: Dict[str, Any] = {
        "pos": pos,
        "human": human_flag,
        "gender": gender,
        "qid": entry.get("qid") or entry.get("wikidata_qid")
    }
    if nat_flag is not None:
        base_features["nationality"] = nat_flag

    # 1. Index the base lemma key
    head_lemma = str(entry.get("lemma") or base_key)
    normalized_map[head_lemma] = dict(base_features)

    # 2. Index all surface forms from the "forms" map
    forms = entry.get("forms")
    if isinstance(forms, Mapping):
        for tag, surface in forms.items():
            if not isinstance(surface, str):
                continue

            feat = dict(base_features)

            # Refine gender/number from tags like "f.sg" / "m.pl"
            if isinstance(tag, str):
                parts = tag.split(".")
                if len(parts) == 2:
                    g_tag, n_tag = parts
                else:
                    g_tag, n_tag = parts[0], None

                g_tag = (g_tag or "").strip()
                n_tag = (n_tag or "").strip() if n_tag else None

                if g_tag in {"m", "f", "n", "common", "neut"}:
                    feat["gender"] = g_tag

                if n_tag in {"sg", "pl"}:
                    feat["number"] = n_tag

            # Add to map
            normalized_map[surface] = feat

    return normalized_map

def _process_file_content(raw_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Extracts valid lemma mappings from a raw file content dict.
    Supports Schema V2 ("entries") and Legacy V1 ("lemmas", "professions", etc).
    """
    extracted_lemmas: Dict[str, Dict[str, Any]] = {}

    # Identify where the entries are stored
    sources = []
    
    # Priority 1: New Standard "entries"
    if "entries" in raw_data and isinstance(raw_data["entries"], Mapping):
        sources.append(raw_data["entries"])
    
    # Priority 2: Legacy "lemmas"
    if "lemmas" in raw_data and isinstance(raw_data["lemmas"], Mapping):
        sources.append(raw_data["lemmas"])

    # Priority 3: Legacy Category Keys (fallback for imperfect migrations)
    for cat in ["professions", "titles", "nationalities", "honours"]:
        if cat in raw_data and isinstance(raw_data[cat], Mapping):
            sources.append(raw_data[cat])

    # Process all found source dictionaries
    for source_dict in sources:
        for key, entry in source_dict.items():
            if isinstance(entry, Mapping):
                # Normalize this single entry into 1+ surface forms
                forms_map = _normalize_entry(key, entry)
                # Merge into main result
                extracted_lemmas.update(forms_map)

    return extracted_lemmas

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_lexicon(lang_code: str) -> Dict[str, Dict[str, Any]]:
    """
    Load and merge all lexicon files for a given language code.

    Scans data/lexicon/{lang_code}/*.json.

    Args:
        lang_code: Language code such as "fr", "pt", "ru".

    Returns:
        A mapping: { "surface_form": { features... }, ... }

    Raises:
        FileNotFoundError: if the language directory does not exist.
    """
    lang_dir = _language_dir(lang_code)
    
    if not lang_dir.is_dir():
        # Fallback check: Does a legacy file exist in the root?
        legacy_file = _lexicon_base_dir() / f"{lang_code}_lexicon.json"
        if legacy_file.is_file():
            logger.warning(f"Loading legacy single-file lexicon for '{lang_code}'")
            raw = _load_json_file(legacy_file)
            return _process_file_content(raw)
            
        raise FileNotFoundError(f"Lexicon directory not found: {lang_dir}")

    master_lexicon: Dict[str, Dict[str, Any]] = {}
    files_processed = 0

    # Iterate over all .json files in the language folder
    # Sort ensures deterministic override order (e.g., core.json vs people.json)
    for file_path in sorted(lang_dir.glob("*.json")):
        raw_data = _load_json_file(file_path)
        if not raw_data:
            continue
            
        file_lemmas = _process_file_content(raw_data)
        master_lexicon.update(file_lemmas)
        files_processed += 1

    if files_processed == 0:
        logger.warning(f"Lexicon folder for '{lang_code}' exists but contains no valid JSON files.")

    return master_lexicon


def available_languages() -> List[str]:
    """
    Return a sorted list of language codes for which a lexicon directory exists.
    """
    lex_dir = _lexicon_base_dir()
    if not lex_dir.is_dir():
        return []

    langs = []
    # Scan for directories that contain at least one .json file
    for item in lex_dir.iterdir():
        if item.is_dir():
            # Check if it has content
            if any(item.glob("*.json")):
                langs.append(item.name)
    
    # Legacy fallback: check for root .json files
    for item in lex_dir.glob("*_lexicon.json"):
        code = item.name.replace("_lexicon.json", "")
        if code not in langs:
            langs.append(code)

    return sorted(langs)


__all__ = [
    "load_lexicon",
    "available_languages",
]