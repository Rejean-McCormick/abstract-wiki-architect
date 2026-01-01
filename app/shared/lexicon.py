import json
import os
import structlog
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field

# Attempt to load settings
try:
    from app.shared.config import settings
except ImportError:
    settings = None

logger = structlog.get_logger()

@dataclass
class LexiconEntry:
    """
    Lightweight data container for a lexical entry.
    Uses __slots__ to optimize memory usage for millions of instances.
    """
    __slots__ = ['lemma', 'pos', 'gf_fun', 'qid', 'source', 'features']
    
    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str]
    source: str
    # Added to support semantic lookups (e.g. P106/Occupation)
    features: Dict[str, Any]

class LexiconRuntime:
    """
    Singleton In-Memory Database for Zone B (Lexicon).
    
    Configuration:
    - Loads 'config/iso_to_wiki.json' to build the 3-letter -> 2-letter normalization map.
    - Lazy loads language shards from 'data/lexicon/{iso2}/'.
    - Loads manual shards (core, people) *over* the bulk harvest (wide).
    """
    _instance = None
    _data: Dict[str, Dict[str, LexiconEntry]] = {} 
    _loaded_langs = set()
    _iso_map: Dict[str, str] = {} # Dynamic Map: 'eng' -> 'en', 'Afr' -> 'af'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LexiconRuntime, cls).__new__(cls)
            cls._instance._load_iso_config()
        return cls._instance

    def _load_iso_config(self):
        """
        Loads 'config/iso_to_wiki.json' to create a unified normalization map.
        This file maps codes to RGL suffixes (e.g., "en": "Eng", "eng": "Eng").
        We reverse this to map everything to the 2-letter ISO code.
        """
        try:
            # Robust Path Resolution logic
            candidates = []

            # 1. Highest Priority: Explicit environment variable/settings override
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "config" / "iso_to_wiki.json")
                candidates.append(repo_root / "config" / "iso_to_wiki.json")

            # 2. Relative to this file's location (app/shared/lexicon.py -> root)
            # This is reliable because the file structure is static within the package
            current_file = Path(__file__).resolve()
            # Walk up from app/shared/lexicon.py to project root
            project_root = current_file.parents[2] 
            candidates.append(project_root / "data" / "config" / "iso_to_wiki.json")
            candidates.append(project_root / "config" / "iso_to_wiki.json")

            # 3. Fallback: Current Working Directory (useful for local dev scripts)
            cwd = Path.cwd()
            candidates.append(cwd / "data" / "config" / "iso_to_wiki.json")
            candidates.append(cwd / "config" / "iso_to_wiki.json")

            config_path = None
            for p in candidates:
                if p.exists():
                    config_path = p
                    break
            
            if config_path:
                with open(config_path, 'r', encoding='utf-8') as f:
                    raw_map = json.load(f)
                    
                # Algorithm: Group keys by their RGL value to find the canonical 2-letter code
                rgl_groups = {}
                for code, rgl_suffix in raw_map.items():
                    if isinstance(rgl_suffix, dict):
                         # v2 format support { "wiki": "Eng", "name": "English" }
                         rgl_suffix = rgl_suffix.get("wiki")
                    
                    if not rgl_suffix: continue

                    if rgl_suffix not in rgl_groups:
                        rgl_groups[rgl_suffix] = []
                    rgl_groups[rgl_suffix].append(code)

                # Build the lookup map
                for rgl_suffix, codes in rgl_groups.items():
                    # Find the 2-letter code to serve as the canonical ID (e.g. 'en')
                    canonical = next((c for c in codes if len(c) == 2), codes[0])
                    
                    # Map the RGL suffix itself (e.g. 'Eng' -> 'en')
                    self._iso_map[rgl_suffix.lower()] = canonical
                    
                    # Map all variants (e.g. 'eng' -> 'en', 'en' -> 'en')
                    for c in codes:
                        self._iso_map[c.lower()] = canonical

                logger.info("lexicon_config_loaded", source=str(config_path), mappings=len(self._iso_map))
            else:
                logger.warning("lexicon_config_missing", searched_paths=[str(c) for c in candidates])
                self._use_fallback_map()

        except Exception as e:
            logger.error("lexicon_init_error", error=str(e))
            self._use_fallback_map()

    def _use_fallback_map(self):
        """Minimal fallback for bootstrapping."""
        self._iso_map = {
            "eng": "en", "fra": "fr", "deu": "de", "nld": "nl", 
            "ita": "it", "spa": "es", "rus": "ru", "swe": "sv",
            "zho": "zh", "jpn": "ja", "ara": "ar", "hin": "hi"
        }

    def _normalize_lang_code(self, code: str) -> str:
        """
        Normalizes any input (ISO-2, ISO-3, RGL Suffix, 'Wiki' prefix) to ISO-2.
        """
        code = code.lower()
        if code.startswith("wiki"):
            code = code[4:]
        
        # 1. Fast Path: Already 2 letters
        if len(code) == 2:
            return code
            
        # 2. Config Lookup
        return self._iso_map.get(code, code[:2])

    def load_language(self, lang_code: str):
        """
        Lazy-loads the lexicon shards for a specific language.
        [FIX] Loads 'wide.json' first, then overrides with 'core', 'people', etc.
        """
        iso2 = self._normalize_lang_code(lang_code)

        if iso2 in self._loaded_langs:
            return

        # Path Resolution
        try:
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                base_path = Path(settings.FILESYSTEM_REPO_PATH)
            else:
                # Use project root derived from file location if settings unavailable
                base_path = Path(__file__).parent.parent.parent
        except Exception:
             base_path = Path("data")

        # Define the load order: Wide (Base) -> Manual Shards (Overrides)
        # This ensures manual fixes in 'people.json' take precedence over 'wide.json'.
        shards_to_load = ["wide.json", "core.json", "people.json", "science.json", "geography.json"]
        
        # Initialize dictionary for this language if not present
        if iso2 not in self._data:
            self._data[iso2] = {}

        total_entries = 0
        loaded_shards = []

        for shard_name in shards_to_load:
            # [FIX] Robust path checking relative to repo root or CWD
            shard_path = base_path / "data" / "lexicon" / iso2 / shard_name
            
            if not shard_path.exists():
                # It's normal for some shards to be missing
                continue

            try:
                with open(shard_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)

                shard_count = 0
                for key, val in raw_data.items():
                    # Handle v1 (list) or v2 (dict) format
                    entry_data = val[0] if isinstance(val, list) else val

                    # Parse features/facts if present
                    features = entry_data.get('features', {})
                    if 'facts' in entry_data:
                        features.update(entry_data['facts'])

                    # Optimization: Create ONE object reference
                    entry_obj = LexiconEntry(
                        lemma=entry_data.get('lemma', 'unknown'),
                        pos=entry_data.get('pos', 'noun'),
                        gf_fun=entry_data.get('gf_fun', ''),
                        qid=entry_data.get('qid') or entry_data.get('wnid'),
                        source=entry_data.get('source', shard_name), # Track which shard it came from
                        features=features
                    )

                    # Store by QID for Ninai lookup (primary index)
                    if entry_obj.qid:
                        self._data[iso2][entry_obj.qid] = entry_obj
                    
                    # Store by Lemma for String lookup (secondary index)
                    # NOTE: Both keys point to the SAME object in memory.
                    # This adds dict overhead but not object overhead.
                    self._data[iso2][entry_obj.lemma.lower()] = entry_obj
                    
                    shard_count += 1

                total_entries += shard_count
                loaded_shards.append(shard_name)

            except json.JSONDecodeError:
                logger.error("lexicon_json_corrupt", lang=iso2, path=str(shard_path))
            except Exception as e:
                logger.error("lexicon_load_failed", lang=iso2, shard=shard_name, error=str(e))

        self._loaded_langs.add(iso2)
        
        if loaded_shards:
            logger.info(
                "lexicon_loaded_success", 
                lang=iso2, 
                total_entries=len(self._data[iso2]),
                shards=loaded_shards
            )
        else:
            logger.warning("lexicon_no_shards_found", lang=iso2)

    def lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        """
        Universal Lookup: Accepts QID (Q42) or Word (Apple).
        """
        if not key: return None
        
        iso2 = self._normalize_lang_code(lang_code)
        self.load_language(iso2)
        
        lang_db = self._data.get(iso2)
        if not lang_db: return None

        return lang_db.get(key) or lang_db.get(key.lower())

    def get_entry(self, lang_code: str, qid: str) -> Optional[LexiconEntry]:
        """
        Alias for lookup, specific for retrieving by QID.
        Called by NinaiAdapter to resolve entities.
        """
        return self.lookup(qid, lang_code)

    def get_facts(self, lang_code: str, qid: str, property_id: str) -> List[str]:
        """
        Retrieves semantic facts (e.g. P106/occupation) for a given entity QID.
        Used by NinaiAdapter to auto-fill frames when data is missing.
        """
        entry = self.get_entry(lang_code, qid)
        if entry and entry.features:
            # Return list of QIDs for the property (e.g. ['Q123', 'Q456'])
            return entry.features.get(property_id, [])
        return []

# --- EXPORT THE SINGLETON ---
lexicon = LexiconRuntime()import json
import os
import structlog
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field

# Attempt to load settings
try:
    from app.shared.config import settings
except ImportError:
    settings = None

logger = structlog.get_logger()

@dataclass
class LexiconEntry:
    """
    Lightweight data container for a lexical entry.
    Uses __slots__ to optimize memory usage for millions of instances.
    """
    __slots__ = ['lemma', 'pos', 'gf_fun', 'qid', 'source', 'features']
    
    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str]
    source: str
    # Added to support semantic lookups (e.g. P106/Occupation)
    features: Dict[str, Any]

class LexiconRuntime:
    """
    Singleton In-Memory Database for Zone B (Lexicon).
    
    Configuration:
    - Loads 'config/iso_to_wiki.json' to build the 3-letter -> 2-letter normalization map.
    - Lazy loads language shards from 'data/lexicon/{iso2}/'.
    - Loads manual shards (core, people) *over* the bulk harvest (wide).
    """
    _instance = None
    _data: Dict[str, Dict[str, LexiconEntry]] = {} 
    _loaded_langs = set()
    _iso_map: Dict[str, str] = {} # Dynamic Map: 'eng' -> 'en', 'Afr' -> 'af'

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LexiconRuntime, cls).__new__(cls)
            cls._instance._load_iso_config()
        return cls._instance

    def _load_iso_config(self):
        """
        Loads 'config/iso_to_wiki.json' to create a unified normalization map.
        This file maps codes to RGL suffixes (e.g., "en": "Eng", "eng": "Eng").
        We reverse this to map everything to the 2-letter ISO code.
        """
        try:
            # Robust Path Resolution logic
            candidates = []

            # 1. Highest Priority: Explicit environment variable/settings override
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                repo_root = Path(settings.FILESYSTEM_REPO_PATH)
                candidates.append(repo_root / "data" / "config" / "iso_to_wiki.json")
                candidates.append(repo_root / "config" / "iso_to_wiki.json")

            # 2. Relative to this file's location (app/shared/lexicon.py -> root)
            # This is reliable because the file structure is static within the package
            current_file = Path(__file__).resolve()
            # Walk up from app/shared/lexicon.py to project root
            project_root = current_file.parents[2] 
            candidates.append(project_root / "data" / "config" / "iso_to_wiki.json")
            candidates.append(project_root / "config" / "iso_to_wiki.json")

            # 3. Fallback: Current Working Directory (useful for local dev scripts)
            cwd = Path.cwd()
            candidates.append(cwd / "data" / "config" / "iso_to_wiki.json")
            candidates.append(cwd / "config" / "iso_to_wiki.json")

            config_path = None
            for p in candidates:
                if p.exists():
                    config_path = p
                    break
            
            if config_path:
                with open(config_path, 'r', encoding='utf-8') as f:
                    raw_map = json.load(f)
                    
                # Algorithm: Group keys by their RGL value to find the canonical 2-letter code
                rgl_groups = {}
                for code, rgl_suffix in raw_map.items():
                    if isinstance(rgl_suffix, dict):
                         # v2 format support { "wiki": "Eng", "name": "English" }
                         rgl_suffix = rgl_suffix.get("wiki")
                    
                    if not rgl_suffix: continue

                    if rgl_suffix not in rgl_groups:
                        rgl_groups[rgl_suffix] = []
                    rgl_groups[rgl_suffix].append(code)

                # Build the lookup map
                for rgl_suffix, codes in rgl_groups.items():
                    # Find the 2-letter code to serve as the canonical ID (e.g. 'en')
                    canonical = next((c for c in codes if len(c) == 2), codes[0])
                    
                    # Map the RGL suffix itself (e.g. 'Eng' -> 'en')
                    self._iso_map[rgl_suffix.lower()] = canonical
                    
                    # Map all variants (e.g. 'eng' -> 'en', 'en' -> 'en')
                    for c in codes:
                        self._iso_map[c.lower()] = canonical

                logger.info("lexicon_config_loaded", source=str(config_path), mappings=len(self._iso_map))
            else:
                logger.warning("lexicon_config_missing", searched_paths=[str(c) for c in candidates])
                self._use_fallback_map()

        except Exception as e:
            logger.error("lexicon_init_error", error=str(e))
            self._use_fallback_map()

    def _use_fallback_map(self):
        """Minimal fallback for bootstrapping."""
        self._iso_map = {
            "eng": "en", "fra": "fr", "deu": "de", "nld": "nl", 
            "ita": "it", "spa": "es", "rus": "ru", "swe": "sv",
            "zho": "zh", "jpn": "ja", "ara": "ar", "hin": "hi"
        }

    def _normalize_lang_code(self, code: str) -> str:
        """
        Normalizes any input (ISO-2, ISO-3, RGL Suffix, 'Wiki' prefix) to ISO-2.
        """
        code = code.lower()
        if code.startswith("wiki"):
            code = code[4:]
        
        # 1. Fast Path: Already 2 letters
        if len(code) == 2:
            return code
            
        # 2. Config Lookup
        return self._iso_map.get(code, code[:2])

    def load_language(self, lang_code: str):
        """
        Lazy-loads the lexicon shards for a specific language.
        [FIX] Loads 'wide.json' first, then overrides with 'core', 'people', etc.
        """
        iso2 = self._normalize_lang_code(lang_code)

        if iso2 in self._loaded_langs:
            return

        # Path Resolution
        try:
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                base_path = Path(settings.FILESYSTEM_REPO_PATH)
            else:
                # Use project root derived from file location if settings unavailable
                base_path = Path(__file__).parent.parent.parent
        except Exception:
             base_path = Path("data")

        # Define the load order: Wide (Base) -> Manual Shards (Overrides)
        # This ensures manual fixes in 'people.json' take precedence over 'wide.json'.
        shards_to_load = ["wide.json", "core.json", "people.json", "science.json", "geography.json"]
        
        # Initialize dictionary for this language if not present
        if iso2 not in self._data:
            self._data[iso2] = {}

        total_entries = 0
        loaded_shards = []

        for shard_name in shards_to_load:
            # [FIX] Robust path checking relative to repo root or CWD
            shard_path = base_path / "data" / "lexicon" / iso2 / shard_name
            
            if not shard_path.exists():
                # It's normal for some shards to be missing
                continue

            try:
                with open(shard_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)

                shard_count = 0
                for key, val in raw_data.items():
                    # Handle v1 (list) or v2 (dict) format
                    entry_data = val[0] if isinstance(val, list) else val

                    # Parse features/facts if present
                    features = entry_data.get('features', {})
                    if 'facts' in entry_data:
                        features.update(entry_data['facts'])

                    # Optimization: Create ONE object reference
                    entry_obj = LexiconEntry(
                        lemma=entry_data.get('lemma', 'unknown'),
                        pos=entry_data.get('pos', 'noun'),
                        gf_fun=entry_data.get('gf_fun', ''),
                        qid=entry_data.get('qid') or entry_data.get('wnid'),
                        source=entry_data.get('source', shard_name), # Track which shard it came from
                        features=features
                    )

                    # Store by QID for Ninai lookup (primary index)
                    if entry_obj.qid:
                        self._data[iso2][entry_obj.qid] = entry_obj
                    
                    # Store by Lemma for String lookup (secondary index)
                    # NOTE: Both keys point to the SAME object in memory.
                    # This adds dict overhead but not object overhead.
                    self._data[iso2][entry_obj.lemma.lower()] = entry_obj
                    
                    shard_count += 1

                total_entries += shard_count
                loaded_shards.append(shard_name)

            except json.JSONDecodeError:
                logger.error("lexicon_json_corrupt", lang=iso2, path=str(shard_path))
            except Exception as e:
                logger.error("lexicon_load_failed", lang=iso2, shard=shard_name, error=str(e))

        self._loaded_langs.add(iso2)
        
        if loaded_shards:
            logger.info(
                "lexicon_loaded_success", 
                lang=iso2, 
                total_entries=len(self._data[iso2]),
                shards=loaded_shards
            )
        else:
            logger.warning("lexicon_no_shards_found", lang=iso2)

    def lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        """
        Universal Lookup: Accepts QID (Q42) or Word (Apple).
        """
        if not key: return None
        
        iso2 = self._normalize_lang_code(lang_code)
        self.load_language(iso2)
        
        lang_db = self._data.get(iso2)
        if not lang_db: return None

        return lang_db.get(key) or lang_db.get(key.lower())

    def get_entry(self, lang_code: str, qid: str) -> Optional[LexiconEntry]:
        """
        Alias for lookup, specific for retrieving by QID.
        Called by NinaiAdapter to resolve entities.
        """
        return self.lookup(qid, lang_code)

    def get_facts(self, lang_code: str, qid: str, property_id: str) -> List[str]:
        """
        Retrieves semantic facts (e.g. P106/occupation) for a given entity QID.
        Used by NinaiAdapter to auto-fill frames when data is missing.
        """
        entry = self.get_entry(lang_code, qid)
        if entry and entry.features:
            # Return list of QIDs for the property (e.g. ['Q123', 'Q456'])
            return entry.features.get(property_id, [])
        return []

# --- EXPORT THE SINGLETON ---
lexicon = LexiconRuntime()