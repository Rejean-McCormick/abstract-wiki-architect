# app/core/ports/llm_port.py
from abc import ABC, abstractmethod
from typing import Optional

class ILanguageModel(ABC):
    """
    Port (Interface) for Language Model interactions.
    Adapters (like GeminiAdapter) must implement this.
    """
    
    @abstractmethod
    def __init__(self, user_api_key: Optional[str] = None):
        """Initialize with an optional API key."""
        pass

    def generate_text(self, prompt: str) -> str:
        """
        Generates text from a prompt.
        Child classes must implement this.
        """
        raise NotImplementedError