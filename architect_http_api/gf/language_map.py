# architect_http_api/gf/language_map.py
# =========================================================================
# LANGUAGE MAPPING: Centralized registry for converting language identifiers
#
# This module converts between:
# 1. Internal Z-Language IDs (used by your system/Wikifunctions)
# 2. ISO 639-1 (2-letter) codes (common public standard)
# 3. ISO 639-3 (3-letter) codes (standard RGL identifiers)
# 4. Legacy RGL Concrete Names (e.g., 'Fre' instead of 'Fra')
#
# =========================================================================

from typing import Dict, List, Optional

# --- 1. CORE DATA MAPPING ---
# Structure: { ISO_639_3 : { 'iso1': ISO_639_1, 'z_id': Z-ID } }
# This list matches the TARGET_LANGUAGES list in gf/build_orchestrator.py
LANGUAGE_MAP: Dict[str, Dict[str, str]] = {
    # --- Tier 1: RGL Core ---
    "eng": {"iso1": "en", "z_id": "Z1002"},
    "fra": {"iso1": "fr", "z_id": "Z1003"},
    "deu": {"iso1": "de", "z_id": "Z1004"},
    "spa": {"iso1": "es", "z_id": "Z1005"},
    "rus": {"iso1": "ru", "z_id": "Z1007"},
    "zho": {"iso1": "zh", "z_id": "Z1008"},
    "jpn": {"iso1": "ja", "z_id": "Z1009"},
    "ara": {"iso1": "ar", "z_id": "Z1011"},
    "hin": {"iso1": "hi", "z_id": "Z1012"},
    "fin": {"iso1": "fi", "z_id": "Z1013"},
    "swe": {"iso1": "sv", "z_id": "Z1014"},
    "swa": {"iso1": "sw", "z_id": "Z1016"},
    "ita": {"iso1": "it", "z_id": "Z1020"},
    "por": {"iso1": "pt", "z_id": "Z1021"},
    "pol": {"iso1": "pl", "z_id": "Z1022"},
    "tur": {"iso1": "tr", "z_id": "Z1023"},
    "bul": {"iso1": "bg", "z_id": "Z1024"},
    "nld": {"iso1": "nl", "z_id": "Z1025"},
    "ron": {"iso1": "ro", "z_id": "Z1026"},
    "dan": {"iso1": "da", "z_id": "Z1027"},
    "nob": {"iso1": "nb", "z_id": "Z1028"},
    "isl": {"iso1": "is", "z_id": "Z1029"},
    "ell": {"iso1": "el", "z_id": "Z1030"},
    "kor": {"iso1": "ko", "z_id": "Z1031"}, # Tier 3 Promoted
    
    # --- Tier 3: Factory / Generated Languages ---
    # We assign Z-IDs sequentially for now (or match Wikidata if known)
    "zul": {"iso1": "zu", "z_id": "Z1032"}, # Zulu
    "yor": {"iso1": "yo", "z_id": "Z1033"}, # Yoruba
    "ibo": {"iso1": "ig", "z_id": "Z1034"}, # Igbo
    "hau": {"iso1": "ha", "z_id": "Z1035"}, # Hausa
    "wol": {"iso1": "wo", "z_id": "Z1036"}, # Wolof
    "kin": {"iso1": "rw", "z_id": "Z1037"}, # Kinyarwanda
    "ind": {"iso1": "id", "z_id": "Z1038"}, # Indonesian
    "msa": {"iso1": "ms", "z_id": "Z1039"}, # Malay
    "tgl": {"iso1": "tl", "z_id": "Z1040"}, # Tagalog
    "vie": {"iso1": "vi", "z_id": "Z1041"}, # Vietnamese
    "que": {"iso1": "qu", "z_id": "Z1042"}, # Quechua
    "aym": {"iso1": "ay", "z_id": "Z1043"}, # Aymara
    "grn": {"iso1": "gn", "z_id": "Z1044"}, # Guarani
    "fry": {"iso1": "fy", "z_id": "Z1045"}, # Frisian
    "bre": {"iso1": "br", "z_id": "Z1046"}, # Breton
    "oci": {"iso1": "oc", "z_id": "Z1047"}, # Occitan
    "gla": {"iso1": "gd", "z_id": "Z1048"}, # Scottish Gaelic
    "cym": {"iso1": "cy", "z_id": "Z1049"}, # Welsh
    "tat": {"iso1": "tt", "z_id": "Z1050"}, # Tatar
    "kur": {"iso1": "ku", "z_id": "Z1051"}, # Kurdish
    # ... extensible list ...
}

# --- 2. LEGACY RGL NAMING RULES ---
# Maps standard ISO 639-3 codes to the specific 3-letter suffix used 
# by the compiled RGL binary (Wiki.pgf).
# Example: 'fra' -> 'Fre' results in concrete grammar 'WikiFre'.
RGL_LEGACY_MAP: Dict[str, str] = {
    "fra": "Fre", "deu": "Ger", "zho": "Chi", "jpn": "Jap",
    "nld": "Dut", "ell": "Gre", "ron": "Rom", "nob": "Nor",
    "swe": "Swe", "dan": "Dan", "isl": "Ice", "fin": "Fin",
    "bul": "Bul", "pol": "Pol", "rus": "Rus", "spa": "Spa",
    "por": "Por", "ita": "Ita", "eng": "Eng", "hin": "Hin",
    "ara": "Ara", "swa": "Swa", "tur": "Tur", "est": "Est",
    "msa": "Msa", "vie": "Vie", "tgl": "Tgl"
}

# --- 3. REVERSE LOOKUP TABLES ---
ISO1_TO_ISO3_MAP: Dict[str, str] = {
    data['iso1']: iso3 for iso3, data in LANGUAGE_MAP.items()
}

ZID_TO_ISO3_MAP: Dict[str, str] = {
    data['z_id']: iso3 for iso3, data in LANGUAGE_MAP.items()
}

# --- PUBLIC FUNCTIONS ---

def get_iso3_code(identifier: str) -> Optional[str]:
    """
    Normalizes any identifier (ISO-1, Z-ID, or ISO-3) to the standard ISO 639-3 code.
    Example: 'en', 'Z1002', 'Eng' -> 'eng'
    """
    ident = identifier.lower().strip()
    
    # 1. Check if already valid ISO-3
    if ident in LANGUAGE_MAP:
        return ident
        
    # 2. Check ISO-1 (2 letters)
    if len(ident) == 2 and ident in ISO1_TO_ISO3_MAP:
        return ISO1_TO_ISO3_MAP[ident]
        
    # 3. Check Z-ID
    if ident.upper() in ZID_TO_ISO3_MAP:
        return ZID_TO_ISO3_MAP[ident.upper()]
        
    # 4. Handle legacy RGL capitalization (e.g. 'Fre' -> 'fra')
    # This is a bit expensive (O(N)), but safe for small N.
    for iso3, legacy in RGL_LEGACY_MAP.items():
        if legacy.lower() == ident:
            return iso3
            
    return None

def get_concrete_name(identifier: str) -> Optional[str]:
    """
    Returns the exact Concrete Grammar name expected by the PGF binary.
    Example: 'fr' -> 'WikiFre', 'zul' -> 'WikiZul'
    """
    iso3 = get_iso3_code(identifier)
    if not iso3:
        return None
        
    # Use legacy map if available, otherwise default to Capitalized ISO-3
    suffix = RGL_LEGACY_MAP.get(iso3, iso3.capitalize())
    return f"Wiki{suffix}"

def get_z_language(identifier: str) -> Optional[str]:
    """Returns the Z-ID for a given language code."""
    iso3 = get_iso3_code(identifier)
    if iso3:
        return LANGUAGE_MAP[iso3]['z_id']
    return None

def get_iso1_code(identifier: str) -> Optional[str]:
    """Returns the ISO 639-1 code for a given language identifier."""
    iso3 = get_iso3_code(identifier)
    if iso3:
        return LANGUAGE_MAP[iso3]['iso1']
    return None

def get_all_supported_codes() -> List[str]:
    """Returns a list of all supported ISO 639-3 codes."""
    return list(LANGUAGE_MAP.keys())