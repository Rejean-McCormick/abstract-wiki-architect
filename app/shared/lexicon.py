import json
import structlog
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from app.shared.config import settings

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
    Maps Abstract IDs (Q42, 02756049-n) -> Concrete Linearizations.
    
    Architecture:
    - Lazy Loading: Only loads languages requested by the API.
    - Sharding: Reads 'wide.json' from the standard 'data/lexicon/{iso2}' directory.
    - Dual Indexing: Supports lookup by QID (Semantic) and Lemma (String).
    """
    _instance = None
    _data: Dict[str, Dict[str, LexiconEntry]] = {} 
    _loaded_langs = set()

    # Enterprise Mapping: RGL (3-letter) -> ISO (2-letter)
    # This ensures that even if the Engine asks for 'eng', we look in 'en'.
    ISO_MAP_3_TO_2 = {
        "eng": "en", "fra": "fr", "deu": "de", "nld": "nl", 
        "ita": "it", "spa": "es", "rus": "ru", "swe": "sv",
        "pol": "pl", "bul": "bg", "ell": "el", "ron": "ro",
        "zho": "zh", "jpn": "ja", "ara": "ar", "hin": "hi",
        "por": "pt", "tur": "tr", "vie": "vi", "kor": "ko"
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LexiconRuntime, cls).__new__(cls)
        return cls._instance

    def _normalize_lang_code(self, code: str) -> str:
        """
        Enforces the ISO 639-1 (2-letter) standard for Data persistence.
        e.g. 'eng' -> 'en', 'WikiFra' -> 'fr', 'fr' -> 'fr'
        """
        code = code.lower()
        # Handle GF prefixes if present
        if code.startswith("wiki"):
            code = code[4:]
        
        # Exact match 2-letter
        if len(code) == 2:
            return code
        
        # Map 3-letter to 2-letter
        if code in self.ISO_MAP_3_TO_2:
            return self.ISO_MAP_3_TO_2[code]
            
        # Fallback (though risky for languages like 'swe'!='sw')
        if len(code) == 3:
            return code[:2]
            
        return code

    def load_language(self, lang_code: str):
        """
        Lazy-loads the massive 'wide.json' shard for a specific language.
        """
        iso2 = self._normalize_lang_code(lang_code)

        if iso2 in self._loaded_langs:
            return

        # Path Resolution: Try settings first, fallback to relative 'data'
        try:
            base_path = Path(settings.FILESYSTEM_REPO_PATH)
        except (AttributeError, TypeError):
            base_path = Path("data")

        # STRICT STANDARD: data/lexicon/{iso2}/wide.json
        shard_path = base_path / "data" / "lexicon" / iso2 / "wide.json"
        
        # Local dev fallback
        if not shard_path.exists():
            local_path = Path("data") / "lexicon" / iso2 / "wide.json"
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
                # Handle list (v1) or dict (v2) format
                entry_data = val[0] if isinstance(val, list) else val

                entry_obj = LexiconEntry(
                    lemma=entry_data.get('lemma', 'unknown'),
                    pos=entry_data.get('pos', 'noun'),
                    gf_fun=entry_data.get('gf_fun', ''),
                    qid=entry_data.get('qid') or entry_data.get('wnid'),
                    source=entry_data.get('source', 'gf-wordnet')
                )

                # Index by QID
                if entry_obj.qid:
                    lang_index[entry_obj.qid] = entry_obj
                
                # Index by Lemma
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

# Global Instance
lexicon_store = LexiconRuntime()