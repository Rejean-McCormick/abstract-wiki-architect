# app/shared/lexicon.py
import json
import structlog
from pathlib import Path
from typing import Dict, Optional, Union, List
from dataclasses import dataclass

from app.shared.config import settings

logger = structlog.get_logger()

@dataclass
class LexiconEntry:
    lemma: str
    pos: str
    gf_fun: str
    qid: Optional[str] = None
    # v2.1: Optional metadata for debugging
    source: str = "unknown"

class LexiconRuntime:
    """
    Singleton In-Memory Database for Zone B (Lexicon).
    Maps Abstract IDs (Q42, 02756049-n) -> Concrete Linearizations.
    
    Architecture:
    - Lazy Loading: Only loads languages requested by the API.
    - Sharding: Reads 'wide.json' (380k+ words) from the data directory.
    - Dual Indexing: Supports lookup by QID (Semantic) and Lemma (String).
    """
    _instance = None
    _data: Dict[str, Dict[str, LexiconEntry]] = {} # {lang_code: {qid_or_lemma: Entry}}
    _loaded_langs = set()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LexiconRuntime, cls).__new__(cls)
        return cls._instance

    def load_language(self, lang_code: str):
        """
        Lazy-loads the massive 'wide.json' shard for a specific language.
        Prevents RAM explosion by only loading requested languages.
        """
        # Normalize language code (e.g. WikiFra -> fra)
        if len(lang_code) > 3:
            lang_code = lang_code[-3:].lower()

        if lang_code in self._loaded_langs:
            return

        # Path: data/lexicon/{lang}/wide.json
        # This matches the output of tools/harvest_lexicon.py
        shard_path = Path(settings.FILESYSTEM_REPO_PATH) / "data" / "lexicon" / lang_code / "wide.json"
        
        if not shard_path.exists():
            # Log warning only once per language
            logger.warning("lexicon_shard_missing", lang=lang_code, path=str(shard_path))
            self._loaded_langs.add(lang_code) # Mark as "attempted" to stop retrying
            return

        try:
            logger.info("lexicon_loading_shard", lang=lang_code)
            with open(shard_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            lang_index = {}
            
            for key, val in raw_data.items():
                # Handle list (v1 harvester) or dict (v2 harvester) format
                # v1: "apple": [{"lemma": "apple", ...}]
                # v2: "apple": {"lemma": "apple", ...}
                entry_data = val[0] if isinstance(val, list) else val

                entry_obj = LexiconEntry(
                    lemma=entry_data.get('lemma', 'unknown'),
                    pos=entry_data.get('pos', 'noun'),
                    gf_fun=entry_data.get('gf_fun', ''),
                    qid=entry_data.get('qid') or entry_data.get('wnid'),
                    source=entry_data.get('source', 'gf-wordnet')
                )

                # Index by QID (Critical for Abstract Wiki: Q42 -> Entry)
                if entry_obj.qid:
                    lang_index[entry_obj.qid] = entry_obj
                
                # Index by Lemma (Fallback: "apple" -> Entry)
                # We lowercase for case-insensitive lookup
                lang_index[entry_obj.lemma.lower()] = entry_obj

            self._data[lang_code] = lang_index
            self._loaded_langs.add(lang_code)
            logger.info("lexicon_loaded_success", lang=lang_code, count=len(lang_index))

        except json.JSONDecodeError:
            logger.error("lexicon_json_corrupt", lang=lang_code, path=str(shard_path))
        except Exception as e:
            logger.error("lexicon_load_failed", lang=lang_code, error=str(e))

    def lookup(self, key: str, lang_code: str) -> Optional[LexiconEntry]:
        """
        Universal Lookup: Accepts QID (Q42) or Word (Apple).
        Returns None if not found or if language shard is missing.
        """
        if not key:
            return None
            
        self.load_language(lang_code)
        
        lang_db = self._data.get(lang_code)
        if not lang_db:
            return None

        # Try exact match (QID is usually case-sensitive "Q42", lemmas are lowercased)
        return lang_db.get(key) or lang_db.get(key.lower())

# Global Instance
lexicon = LexiconRuntime()