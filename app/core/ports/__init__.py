# app/core/ports/__init__.py
from typing import Any, Dict, List, Optional, Protocol, Union

# [FIX] Import Frame from models, NOT from frame.py
from app.core.domain.models import Sentence, Frame
from app.core.domain.events import SystemEvent

# ==============================================================================
# AI & GENERATION PORTS
# ==============================================================================

class IGrammarEngine(Protocol):
    """
    Interface for the Abstract Wikipedia Grammar Engine (GF/PGF).
    """
    grammar: Any  # Exposes the underlying PGF object if needed

    async def generate(self, lang_code: str, frame: Union[Frame, Dict[str, Any]]) -> Sentence:
        """Generates text from an abstract frame."""
        ...

    async def get_supported_languages(self) -> List[str]:
        """Returns list of supported ISO 639-3 codes (e.g. ['eng', 'deu'])."""
        ...

    async def reload(self) -> None:
        """Hot-reloads the grammar from disk."""
        ...

    async def health_check(self) -> bool:
        """Returns True if engine is operational."""
        ...


class LLMPort(Protocol):
    """
    Interface for Large Language Models (AI Services).
    """
    def generate_text(self, prompt: str) -> str:
        """Send a prompt to the LLM and get the response text."""
        ...


# ==============================================================================
# INFRASTRUCTURE PORTS
# ==============================================================================

class IMessageBroker(Protocol):
    """
    Interface for Event Bus (Pub/Sub).
    """
    async def publish(self, event: Any) -> None:
        ...

    async def subscribe(self, channel: str, handler: Any) -> None:
        ...

    async def connect(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    async def health_check(self) -> bool:
        ...


class TaskQueue(Protocol):
    """
    Interface for Async Job Queue (e.g., Redis/ARQ).
    """
    async def connect(self) -> None:
        ...

    async def disconnect(self) -> None:
        ...

    async def enqueue(self, function_name: str, **kwargs) -> Optional[str]:
        """
        Enqueues a job.
        :param function_name: The name of the worker function to execute.
        :param kwargs: Arguments to pass to the function.
        :return: Job ID or None.
        """
        ...


# ==============================================================================
# REPOSITORY PORTS
# ==============================================================================

class LexiconRepo(Protocol):
    """
    Interface for Lexical Knowledge Base (Entries, Lemmas).
    """
    async def get_entry(self, lang: str, key: str) -> Optional[Dict[str, Any]]:
        ...

    async def save_entry(self, lang: str, entry: Dict[str, Any]) -> None:
        ...

    async def health_check(self) -> bool:
        ...


class LanguageRepo(Protocol):
    """
    Interface for Language Metadata & Grammar Registry.
    """
    async def save_grammar(self, code: str, metadata_json: str) -> None:
        """Persists language configuration/metadata."""
        ...

    async def list_languages(self) -> List[Dict[str, Any]]:
        """Returns list of onboarded languages."""
        ...

    async def health_check(self) -> bool:
        ...

# ==============================================================================
# EXPORTS
# ==============================================================================
__all__ = [
    "LanguageRepo",
    "LexiconRepo",
    "IGrammarEngine",
    "LLMPort",
    "IMessageBroker",
    "TaskQueue",
]