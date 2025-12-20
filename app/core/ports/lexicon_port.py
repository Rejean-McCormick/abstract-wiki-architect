# app/core/ports/lexicon_port.py
from abc import ABC, abstractmethod
from typing import Optional, List
from app.core.domain.models import LexiconEntry

class ILexiconRepository(ABC):
    """
    Interface (Port) for accessing the Lexicon persistence layer.
    """
    
    @abstractmethod
    async def get_entry(self, iso_code: str, word: str) -> Optional[LexiconEntry]:
        """Retrieves a single lexicon entry by word/lemma."""
        pass

    @abstractmethod
    async def save_entry(self, iso_code: str, entry: LexiconEntry) -> None:
        """Saves or updates a lexicon entry."""
        pass

    @abstractmethod
    async def get_entries_by_concept(self, lang_code: str, qid: str) -> List[LexiconEntry]:
        """Finds all entries linked to a specific Wikidata QID."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verifies connection to storage."""
        pass