# app\core\domain\models.py
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

# --- Enums ---

class LanguageStatus(str, Enum):
    """Lifecycle status of a language in the system."""
    PLANNED = "planned"       # Defined in config but no files exist
    SCAFFOLDED = "scaffolded" # Directories created, seed files exist
    BUILDING = "building"     # Compilation in progress
    READY = "ready"           # Successfully compiled and loaded
    ERROR = "error"           # Build failed

class GrammarType(str, Enum):
    """The type of grammar engine backing a language."""
    RGL = "rgl"               # Official Resource Grammar Library
    CONTRIB = "contrib"       # Manual contribution (Silver tier)
    FACTORY = "factory"       # Auto-generated Pidgin (Bronze tier)

# --- Entities ---

class Language(BaseModel):
    """
    Represents a supported language in the system.
    Matches the data found in the 'Everything Matrix'.
    """
    code: str = Field(..., description="ISO 639-3 code (e.g., 'fra', 'zul')")
    name: str = Field(..., description="English name of the language")
    family: Optional[str] = Field(None, description="Language family (e.g., 'Romance')")
    status: LanguageStatus = LanguageStatus.PLANNED
    grammar_type: GrammarType = GrammarType.FACTORY
    
    # Metadata for tracking build health
    build_strategy: str = "fast"  # 'fast' or 'full'
    last_build_time: Optional[datetime] = None
    error_log: Optional[str] = None

class Frame(BaseModel):
    """
    The input semantic frame representing the abstract intent.
    This is what the frontend sends to the backend.
    """
    frame_type: str = Field(..., description="The schema type (e.g., 'bio', 'event')")
    
    # The primary subject of the frame (e.g., the person in a bio)
    subject: Dict[str, Any] = Field(default_factory=dict)
    
    # Additional properties (e.g., profession, nationality, date)
    properties: Dict[str, Any] = Field(default_factory=dict)
    
    # Contextual hints for the renderer (e.g., tense, formality)
    meta: Dict[str, Any] = Field(default_factory=dict)

class Sentence(BaseModel):
    """
    The output generated text.
    """
    text: str
    lang_code: str
    
    # Debug info provided by the engine (e.g., linearization tree)
    debug_info: Optional[Dict[str, Any]] = None
    
    # Metrics for observability
    generation_time_ms: float = 0.0

class LexiconEntry(BaseModel):
    """
    Represents a single word in the lexicon.
    """
    lemma: str
    pos: str  # Part of Speech: N, V, A, etc.
    features: Dict[str, Any] = Field(default_factory=dict) # Gender, Number, etc.
    source: str = "manual" # 'wikidata', 'ai', 'manual'
    confidence: float = 1.0