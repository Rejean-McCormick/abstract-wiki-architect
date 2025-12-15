# app\core\ports\lexicon_repository.py
from typing import Protocol, Optional, Dict, List
from app.core.domain.models import LexiconEntry

class ILexiconRepository(Protocol):
    """
    Port for accessing Lexicon data.
    Implementations could be FileSystemRepo, SqlAlchemyRepo, or WikidataAdapter.
    """

    async def get_entry(self, lang_code: str, lemma: str) -> Optional[LexiconEntry]:
        """
        Retrieves a single lexicon entry by lemma.
        
        Args:
            lang_code: The ISO 639-3 language code (e.g., 'fra').
            lemma: The dictionary form of the word.
            
        Returns:
            The LexiconEntry if found, None otherwise.
        """
        ...

    async def get_entries_by_concept(self, lang_code: str, qid: str) -> List[LexiconEntry]:
        """
        Retrieves all entries linked to a specific Abstract Concept (QID).
        
        Args:
            lang_code: The ISO 639-3 language code.
            qid: The Wikidata QID (e.g., 'Q42').
            
        Returns:
            A list of matching entries (synonyms).
        """
        ...

    async def save_entry(self, lang_code: str, entry: LexiconEntry) -> None:
        """
        Persists a new entry to the lexicon.
        """
        ...

    async def health_check(self) -> bool:
        """Returns True if the underlying storage is accessible."""
        ...