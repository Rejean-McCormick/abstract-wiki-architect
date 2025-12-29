import json
import structlog
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

# Attempt to load settings
try:
    from app.shared.config import settings
except ImportError:
    settings = None

logger = structlog.get_logger()

@dataclass
class LexiconEntry:
    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str] = None
    source: str = "unknown"

class LexiconRuntime:
    """
    Singleton In-Memory Database for Zone B (Lexicon).
    
    Configuration:
    - Loads 'config/iso_to_wiki.json' to build the 3-letter -> 2-letter normalization map.
    - Lazy loads language shards from 'data/lexicon/{iso2}/wide.json'.
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
            # Path Resolution: ../../config/iso_to_wiki.json
            root = Path(__file__).parent.parent.parent
            config_path = root / "config" / "iso_to_wiki.json"
            
            if config_path.exists():
                with open(config_path, 'r') as f:
                    raw_map = json.load(f)
                    
                # Algorithm: Group keys by their RGL value to find the canonical 2-letter code
                # rgl_groups = {'Eng': ['en', 'eng'], 'Afr': ['af', 'afr']}
                rgl_groups = {}
                for code, rgl_suffix in raw_map.items():
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
                logger.warning("lexicon_config_missing", path=str(config_path))
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
        
        # 1. Fast Path: Already 2 letters (and assume it's valid if not in map, or check map)
        if len(code) == 2:
            return code
            
        # 2. Config Lookup
        return self._iso_map.get(code, code[:2])

    def load_language(self, lang_code: str):
        """
        Lazy-loads the massive 'wide.json' shard for a specific language.
        """
        iso2 = self._normalize_lang_code(lang_code)

        if iso2 in self._loaded_langs:
            return

        # Path Resolution
        try:
            if settings and hasattr(settings, 'FILESYSTEM_REPO_PATH'):
                base_path = Path(settings.FILESYSTEM_REPO_PATH)
            else:
                base_path = Path("data") # Fallback for worker context
        except Exception:
            base_path = Path("data")

        # STRICT STANDARD: data/lexicon/{iso2}/wide.json
        shard_path = base_path / "data" / "lexicon" / iso2 / "wide.json"
        
        # Local dev fallback check
        if not shard_path.exists():
            local_root = Path(__file__).parent.parent.parent
            local_path = local_root / "data" / "lexicon" / iso2 / "wide.json"
            if local_path.exists():
                shard_path = local_path

        if not shard_path.exists():
            # Log warning only once per language
            logger.warning("lexicon_shard_missing", lang=iso2, path=str(shard_path))
            self._loaded_langs.add(iso2) 
            return

        try:
            logger.info("lexicon_loading_shard", lang=iso2, path=str(shard_path))
            with open(shard_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            lang_index = {}
            
            for key, val in raw_data.items():
                # Handle v1 (list) or v2 (dict) format
                entry_data = val[0] if isinstance(val, list) else val

                entry_obj = LexiconEntry(
                    lemma=entry_data.get('lemma', 'unknown'),
                    pos=entry_data.get('pos', 'noun'),
                    gf_fun=entry_data.get('gf_fun', ''),
                    qid=entry_data.get('qid') or entry_data.get('wnid'),
                    source=entry_data.get('source', 'gf-wordnet')
                )

                if entry_obj.qid:
                    lang_index[entry_obj.qid] = entry_obj
                
                lang_index[entry_obj.lemma.lower()] = entry_obj

            self._data[iso2] = lang_index
            self._loaded_langs.add(iso2)
            logger.info("lexicon_loaded_success", lang=iso2, count=len(lang_index))

        except json.JSONDecodeError:
            logger.error("lexicon_json_corrupt", lang=iso2, path=str(shard_path))
        except Exception as e:
            logger.error("lexicon_load_failed", lang=iso2, error=str(e))

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

# --- EXPORT THE SINGLETON ---
lexicon = LexiconRuntime()