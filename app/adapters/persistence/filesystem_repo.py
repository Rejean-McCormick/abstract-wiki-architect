# app/adapters/persistence/filesystem_repo.py
import json
import os
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog

# Ensure this import matches your actual Port file name. 
# If you renamed it to 'lexicon_port.py', update this line accordingly.
from app.core.ports.lexicon_port import ILexiconRepository
from app.core.domain.models import LexiconEntry
from app.core.domain.exceptions import LexiconEntryNotFoundError
from app.shared.config import settings

logger = structlog.get_logger()

class FileSystemLexiconRepository(ILexiconRepository):
    """
    Concrete implementation of the Lexicon Repository using local JSON files.
    """

    # FIX: Added 'base_path' argument to satisfy the Dependency Injector
    def __init__(self, base_path: str):
        # We use the injected base_path (from config) and append /lexicon
        self.base_path = Path(base_path) / "data" / "lexicon"
        # Ensure the directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, lang_code: str) -> Path:
        # Structure: .../data/lexicon/fra/lexicon.json
        # Using subfolders prevents massive directory clutter
        return self.base_path / lang_code / "lexicon.json"

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
        
        # Ensure the language subdirectory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error("repo_write_failed", lang=lang_code, error=str(e))
            raise IOError(f"Could not save lexicon for {lang_code}")

    # --- Interface Implementation ---

    async def get_entry(self, iso_code: str, word: str) -> Optional[LexiconEntry]:
        # Note: In your original code you used 'lemma' as the argument name, 
        # but the interface likely expects 'word' or 'lemma'. We map it here.
        data = await self._load_file(iso_code)
        
        raw_entry = data.get(word)
        if not raw_entry:
            return None
            
        return LexiconEntry(**raw_entry)

    async def get_entries_by_concept(self, lang_code: str, qid: str) -> List[LexiconEntry]:
        """
        Scans the language file for entries linked to a specific QID.
        """
        data = await self._load_file(lang_code)
        results = []

        for key, raw_entry in data.items():
            # Check if the entry has a list of linked concepts
            concepts = raw_entry.get("concepts", [])
            if qid in concepts:
                results.append(LexiconEntry(**raw_entry))
                
        return results

    async def save_entry(self, iso_code: str, entry: LexiconEntry) -> None:
        """
        Upserts an entry into the JSON file.
        """
        # 1. Load existing
        data = await self._load_file(iso_code)
        
        # 2. Update/Insert
        # Using entry.lemma (or entry.word) as the key.
        # We try 'model_dump' (Pydantic v2) then 'dict' (v1)
        try:
            val = entry.model_dump()
        except AttributeError:
            val = entry.dict()

        # We use the lemma as the primary key in the JSON dict
        key = entry.lemma if entry.lemma else entry.word
        data[key] = val
        
        # 3. Write back
        await self._save_file(iso_code, data)
        
        logger.info("lexicon_entry_saved", lang=iso_code, lemma=key)

    async def health_check(self) -> bool:
        """Checks if the data directory is accessible."""
        return self.base_path.exists() and os.access(self.base_path, os.R_OK)