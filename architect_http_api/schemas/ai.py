# architect_http_api/schemas/ai.py

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from .common import BaseApiModel

JSONDict = Dict[str, Any]

# ---------------------------------------------------------------------------
# NEW: Assistant / Panel Schemas (Your provided code)
# ---------------------------------------------------------------------------

class AISuggestionKind(str, Enum):
    """
    Coarse categories for structured AI suggestions.
    The frontend can use this to choose icons, colors, or sections in the UI.
    """
    FRAME_TEMPLATE = "frame_template"
    FIELD_HELP = "field_help"
    OUTPUT_EXPLANATION = "output_explanation"
    NEXT_STEP = "next_step"
    WARNING = "warning"
    ERROR = "error"


class AIFrameContext(BaseModel):
    """Snapshot of the currently active frame in the UI."""
    frame_slug: Optional[str] = Field(None, description="UI-facing identifier (e.g. 'bio').")
    frame_type: Optional[str] = Field(None, description="Canonical NLG frame_type discriminator.")
    payload: JSONDict = Field(default_factory=dict, description="Current frame JSON payload.")


class AIGenerationContext(BaseModel):
    """Context about the latest NLG generation shown to the user."""
    lang: Optional[str] = Field(None, description="Language code used.")
    text: Optional[str] = Field(None, description="Last generated surface text.")
    debug_info: JSONDict = Field(default_factory=dict, description="Optional debug/metadata.")


class AIUserProfile(BaseModel):
    """Lightweight, optional hints about the human behind the session."""
    role: Optional[str] = Field(None)
    experience_level: Optional[str] = Field(None)
    locale: Optional[str] = Field(None)
    extra: JSONDict = Field(default_factory=dict)


class AIConversationMessage(BaseModel):
    """Single message in the side-panel conversation."""
    role: str = Field(..., pattern=r"^(user|assistant|system)$")
    content: str = Field(...)


class AIAssistRequest(BaseModel):
    """Main request shape for the /ai/assist endpoint."""
    user_query: str
    lang: Optional[str] = None
    frame: Optional[AIFrameContext] = None
    last_generation: Optional[AIGenerationContext] = None
    user: Optional[AIUserProfile] = None
    conversation: List[AIConversationMessage] = Field(default_factory=list)
    extra: JSONDict = Field(default_factory=dict)


class AISuggestion(BaseModel):
    """Structured suggestion emitted by the AI assistant."""
    id: str
    kind: AISuggestionKind
    title: str
    body: str
    score: Optional[float] = None
    highlight_fields: List[str] = Field(default_factory=list)
    frame_patch: JSONDict = Field(default_factory=dict)
    follow_up_question: Optional[str] = None
    follow_up_hints: List[str] = Field(default_factory=list)


class AIQuickAction(BaseModel):
    """Pre-baked quick action that the UI can show as buttons."""
    id: str
    label: str
    description: Optional[str] = None
    frame_slug: Optional[str] = None
    initial_frame_payload: JSONDict = Field(default_factory=dict)
    extra: JSONDict = Field(default_factory=dict)


class AIAssistResponse(BaseModel):
    """Response shape for the /ai/assist endpoint."""
    assistant_reply: str
    suggestions: List[AISuggestion] = Field(default_factory=list)
    quick_actions: List[AIQuickAction] = Field(default_factory=list)
    conversation: List[AIConversationMessage] = Field(default_factory=list)
    debug_info: JSONDict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# MISSING SCHEMAS: Required by routers, intent_handler, and __init__.py
# ---------------------------------------------------------------------------

class IntentKind(str, Enum):
    """Categories of user intent inferred from natural language."""
    CREATE_FRAME = "create_frame"
    EDIT_FRAME = "edit_frame"
    EXPLAIN = "explain"
    UNKNOWN = "unknown"

class IntentInput(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class IntentResult(BaseModel):
    kind: IntentKind
    confidence: float
    parameters: Dict[str, Any] = Field(default_factory=dict)


# --- Command / Intent Handler Schemas ---

class AICommandRequest(BaseModel):
    """Request model for inferring intent from a user command."""
    workspace_slug: Optional[str] = None
    lang: str = "en"
    message: str
    context_frame: Optional[Dict[str, Any]] = None
    debug: bool = False

class AIFramePatch(BaseModel):
    """Represents a suggested change to a frame."""
    path: str = Field(..., description="Dotted path to the field (e.g. 'birth_event.date')")
    value: Any = Field(..., description="New value for the field")
    op: str = Field("replace", description="Operation: replace, append, etc.")

class AIMessage(BaseModel):
    """Simple message wrapper for command responses (Legacy)."""
    role: str
    content: str

class AICommandResponse(BaseModel):
    """Response from the intent handler."""
    workspace_slug: Optional[str] = None
    lang: str
    user_message: str
    assistant_messages: List[AIMessage] = Field(default_factory=list)
    intent_label: Optional[str] = None
    patches: List[AIFramePatch] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None

class AIIntentModelResponse(BaseModel):
    """Intermediate response from the AI Client service."""
    intent_label: str
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    assistant_messages: List[AIMessage] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None


# --- Router Request/Response Models ---

class AISuggestFieldsRequest(BaseModel):
    frame_type: str
    current_payload: Dict[str, Any] = Field(default_factory=dict)
    user_instruction: Optional[str] = None
    lang: str = "en"

class AISuggestFieldsResponse(BaseModel):
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)

class AIExplainRequest(BaseModel):
    lang: str
    frame_type: str
    frame: Dict[str, Any]
    target_field: Optional[str] = None
    generation_text: Optional[str] = None

class AIExplainResponse(BaseModel):
    explanation: List[Dict[str, Any]]


# --- Aliases for Backward Compatibility ---

# Routers often import these specific names
AIIntentRequest = AICommandRequest
AIIntentResponse = AICommandResponse
AISuggestionRequest = AISuggestFieldsRequest
AISuggestionResponse = AISuggestFieldsResponse