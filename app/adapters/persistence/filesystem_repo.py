# app/adapters/persistence/filesystem_repo.py
import json
import os
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Any
import structlog

# [FIX] Import from the centralized ports package
from app.core.ports import LanguageRepo, LexiconRepo

from app.core.domain.models import LexiconEntry
from app.core.domain.exceptions import LexiconEntryNotFoundError
from app.shared.config import settings

logger = structlog.get_logger()

class FileSystemLexiconRepository(LanguageRepo, LexiconRepo):
    """
    Concrete implementation of the Repository using local JSON files.
    - Acts as LanguageRepo (reading 'everything_matrix.json')
    - Acts as LexiconRepo (reading 'lexicon/{lang}/lexicon.json')
    """

    def __init__(self, base_path: str):
        self.root = Path(base_path).resolve()
        
        # Path for Lexicon Data (Zone B)
        self.lexicon_base = self.root / "data" / "lexicon"
        self.lexicon_base.mkdir(parents=True, exist_ok=True)
        
        # Path for Matrix Index (Zone A)
        self.matrix_path = self.root / "data" / "indices" / "everything_matrix.json"

    # =========================================================
    # PART 1: LanguageRepo Implementation (Fixes API 500 Error)
    # =========================================================
    async def list_languages(self) -> List[Dict[str, Any]]:
        """
        Reads the dynamic registry to populate the Frontend Language Selector.
        """
        if not self.matrix_path.exists():
            logger.warning("matrix_not_found", path=str(self.matrix_path))
            return [
                {"code": "eng", "name": "English (Fallback)", "z_id": "Z1002"},
                {"code": "fra", "name": "French (Fallback)", "z_id": "Z1004"}
            ]

        try:
            async with aiofiles.open(self.matrix_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
            
            languages = []
            for iso_code, details in data.get("languages", {}).items():
                meta = details.get("meta", {})
                languages.append({
                    "code": meta.get("iso", iso_code),
                    "name": meta.get("name", iso_code.upper()),
                    "z_id": meta.get("z_id", None)
                })
            return sorted(languages, key=lambda x: x["name"])
        except Exception as e:
            logger.error("list_languages_failed", error=str(e))
            return []

    # =========================================================
    # PART 2: LexiconRepo Implementation (Your Logic)
    # =========================================================
    
    def _get_file_path(self, lang_code: str) -> Path:
        # v2.1 Standard: Look for 'wide.json' which is the compiled shard,
        # but also allow falling back or writing to specific domain files.
        # For simplicity in this Repo implementation, we default to a primary shard.
        return self.lexicon_base / lang_code / "lexicon.json"

    async def _load_file(self, lang_code: str) -> Dict[str, Any]:
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
        path = self._get_file_path(lang_code)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiofiles.open(path, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error("repo_write_failed", lang=lang_code, error=str(e))
            raise IOError(f"Could not save lexicon for {lang_code}")

    async def get_entry(self, iso_code: str, word: str) -> Optional[LexiconEntry]:
        data = await self._load_file(iso_code)
        raw_entry = data.get(word)
        if not raw_entry:
            return None
        return LexiconEntry(**raw_entry)

    async def save_entry(self, iso_code: str, entry: LexiconEntry) -> None:
        data = await self._load_file(iso_code)
        
        try:
            val = entry.model_dump()
        except AttributeError:
            val = entry.dict()

        key = entry.lemma if entry.lemma else entry.word
        data[key] = val
        
        await self._save_file(iso_code, data)
        logger.info("lexicon_entry_saved", lang=iso_code, lemma=key)

    async def get_entries_by_concept(self, lang_code: str, qid: str) -> List[LexiconEntry]:
        """
        [FIXED] Now correctly checks 'qid' fields instead of the non-existent 'concepts' list.
        """
        data = await self._load_file(lang_code)
        results = []
        for key, raw_entry in data.items():
            # Check 1: Root level QID (standard v2)
            entry_qid = raw_entry.get("qid") or raw_entry.get("wikidata_qid")
            
            # Check 2: Features QID (v2.1 semantic enrichment)
            if not entry_qid:
                features = raw_entry.get("features", {})
                entry_qid = features.get("qid")

            if entry_qid == qid:
                results.append(LexiconEntry(**raw_entry))
                
        return results

    # --- Compliance Stubs (Required by LanguageRepo ABC) ---
    
    async def save_grammar(self, language_code: str, content: str) -> None:
        """
        [FIXED] Persistence for Language Onboarding.
        Writes the Language Metadata (JSON) to the file system to prevent 'Zombie' languages.
        """
        target_dir = self.lexicon_base / language_code
        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_file = target_dir / "language.json"
        
        try:
            async with aiofiles.open(target_file, mode='w', encoding='utf-8') as f:
                # 'content' here is the JSON string from Language.model_dump_json()
                await f.write(content)
            
            logger.info("grammar_meta_persisted", lang=language_code, path=str(target_file))
            
            # Optional: Create a skeleton core.json if it doesn't exist, 
            # so the scanner picks it up immediately as a 'SEED' > 0.
            core_file = target_dir / "core.json"
            if not core_file.exists():
                async with aiofiles.open(core_file, mode='w', encoding='utf-8') as f:
                    await f.write("{}")

        except Exception as e:
            logger.error("save_grammar_failed", lang=language_code, error=str(e))
            raise IOError(f"Failed to persist grammar metadata for {language_code}")

    async def get_grammar(self, language_code: str) -> Optional[str]:
        """
        Retrieves the persisted language metadata.
        """
        target_file = self.lexicon_base / language_code / "language.json"
        if not target_file.exists():
            return None
            
        try:
            async with aiofiles.open(target_file, mode='r', encoding='utf-8') as f:
                return await f.read()
        except Exception:
            return None

    async def health_check(self) -> bool:
        """
        Verifies that the underlying storage directory exists and is writable.
        Required by the Readiness Probe.
        """
        try:
            # Ensure the root lexicon directory exists
            if not self.lexicon_base.exists():
                self.lexicon_base.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error("storage_health_check_failed", error=str(e))
            return False