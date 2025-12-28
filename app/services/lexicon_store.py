
import json
import structlog
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = structlog.get_logger()

class LexiconStore:
    """
    In-Memory Cache for Zone B (Lexicon) Data.
    Standard Path: data/lexicon/{lang}/*.json
    """
    _cache: Dict[str, Dict[str, Any]] = {}
    
    # PERMANENT FIX: Point to the project root 'data' folder
    BASE_PATH = Path("data/lexicon")

    @classmethod
    def get_lemma(cls, lang_code: str, qid: str) -> str:
        """
        Returns the lemma for a QID (e.g., 'Alan Turing').
        """
        entry = cls.get_entry(lang_code, qid)
        if entry:
             # Handle both simple string values or complex dicts with "lemma"
            if isinstance(entry, dict):
                return entry.get("lemma", qid)
            return str(entry)
            
        return qid # Fallback to "Q42" if truly missing

    @classmethod
    def get_facts(cls, lang_code: str, qid: str, property_id: str) -> List[str]:
        """
        Returns a list of QIDs for a semantic property.
        Example: get_facts('eng', 'Q7251', 'P106') -> ['Q123'] (Mathematician)
        """
        entry = cls.get_entry(lang_code, qid)
        if isinstance(entry, dict):
            facts = entry.get("facts", {})
            # Return the list of QIDs for the requested property (e.g. P106)
            return facts.get(property_id, [])
        return []

    @classmethod
    def get_entry(cls, lang_code: str, qid: str) -> Optional[Any]:
        """
        Returns the full dictionary entry for a QID, handling lazy loading.
        """
        # Lazy Load Language if not in cache
        if lang_code not in cls._cache:
            cls._load_language(lang_code)
            
        return cls._cache.get(lang_code, {}).get(qid)

    @classmethod
    def _load_language(cls, lang: str):
        logger.info("lexicon_hydrating", lang=lang)
        cls._cache[lang] = {}
        
        target_dir = cls.BASE_PATH / lang
        
        if not target_dir.exists():
            logger.warning("lexicon_dir_missing", path=str(target_dir))
            return

        # 1. Load all JSON shards in the folder (people.json, wide.json, etc.)
        loaded_count = 0
        for file_path in target_dir.glob("*.json"):
            if file_path.name == "overrides.json":
                continue # Load this last
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    cls._cache[lang].update(data)
                    loaded_count += 1
            except Exception as e:
                logger.error("lexicon_shard_error", file=file_path.name, error=str(e))

        # 2. Load Overrides (Last to ensure priority)
        override_path = target_dir / "overrides.json"
        if override_path.exists():
            try:
                with open(override_path, 'r', encoding='utf-8') as f:
                    cls._cache[lang].update(json.load(f))
                    logger.info("lexicon_overrides_loaded", lang=lang)
            except Exception as e:
                 logger.error("lexicon_override_error", error=str(e))
                 
        logger.info("lexicon_ready", lang=lang, shards_loaded=loaded_count, total_entries=len(cls._cache[lang]))
