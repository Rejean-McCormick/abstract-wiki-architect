# app\adapters\persistence\filesystem_repo.py
import json
import os
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog

from app.core.ports.lexicon_repository import ILexiconRepository
from app.core.domain.models import LexiconEntry
from app.core.domain.exceptions import LexiconEntryNotFoundError
from app.shared.config import settings

logger = structlog.get_logger()

class FileSystemLexiconRepository(ILexiconRepository):
    """
    Concrete implementation of the Lexicon Repository using local JSON files.
    
    File Structure:
    {FILESYSTEM_REPO_PATH}/lexicon/{lang_code}.json
    
    Format:
    {
        "lemma_key": {
            "lemma": "word",
            "pos": "N",
            "features": {...},
            "concepts": ["Q42"] 
        }
    }
    """

    def __init__(self):
        self.base_path = Path(settings.FILESYSTEM_REPO_PATH) / "lexicon"
        # Ensure the directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, lang_code: str) -> Path:
        return self.base_path / f"{lang_code}.json"

    async def _load_file(self, lang_code: str) -> Dict[str, Any]:
        """Helper to load raw JSON data for a language."""
        path = self._get_file_path(lang_code)
        if not path.exists():
            return {}
        
        try:
            async with aiofiles.open(path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except Exception as e:
            logger.error("repo_read_failed", lang=lang_code, error=str(e))
            return {}

    async def _save_file(self, lang_code: str, data: Dict[str, Any]) -> None:
        """Helper to write raw JSON data safely."""
        path = self._get_file_path(lang_code)
        try:
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error("repo_write_failed", lang=lang_code, error=str(e))
            raise IOError(f"Could not save lexicon for {lang_code}")

    # --- Interface Implementation ---

    async def get_entry(self, lang_code: str, lemma: str) -> Optional[LexiconEntry]:
        data = await self._load_file(lang_code)
        
        # We assume the JSON is keyed by lemma for O(1) access
        raw_entry = data.get(lemma)
        
        if not raw_entry:
            return None
            
        return LexiconEntry(**raw_entry)

    async def get_entries_by_concept(self, lang_code: str, qid: str) -> List[LexiconEntry]:
        """
        Scans the language file for entries linked to a specific QID.
        Note: This is O(N) for files. A real DB would use an index.
        """
        data = await self._load_file(lang_code)
        results = []

        for key, raw_entry in data.items():
            # Check if the entry has a list of linked concepts
            concepts = raw_entry.get("concepts", [])
            if qid in concepts:
                results.append(LexiconEntry(**raw_entry))
                
        return results

    async def save_entry(self, lang_code: str, entry: LexiconEntry) -> None:
        """
        Upserts an entry into the JSON file.
        """
        # 1. Load existing
        data = await self._load_file(lang_code)
        
        # 2. Update/Insert
        # Using lemma as the key. 
        # In a complex morph system, key might be 'lemma+pos'.
        data[entry.lemma] = entry.model_dump()
        
        # 3. Write back
        await self._save_file(lang_code, data)
        
        logger.info("lexicon_entry_saved", lang=lang_code, lemma=entry.lemma)

    async def health_check(self) -> bool:
        """Checks if the data directory is accessible."""
        return self.base_path.exists() and os.access(self.base_path, os.R_OK)