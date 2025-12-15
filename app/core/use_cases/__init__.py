# app\core\use_cases\__init__.py
"""
Core Use Cases (Application Logic).

This package contains the "Interactors" of the system. They orchestrate
the flow of data between the Domain Entities and the Infrastructure Ports.
Each use case represents a specific business action (e.g., "Generate Text",
"Onboard New Language") and is responsible for:
1. Validating input/request models.
2. Interacting with Ports (Lexicon, Engine, Broker).
3. Returning Domain Entities or Events.
"""

from .generate_text import GenerateText
from .build_language import BuildLanguage
from .onboard_language_saga import OnboardLanguageSaga

__all__ = [
    "GenerateText",
    "BuildLanguage",
    "OnboardLanguageSaga",
]