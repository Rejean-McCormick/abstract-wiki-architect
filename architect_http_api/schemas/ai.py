# architect_http_api/schemas/ai.py

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


JSONDict = Dict[str, Any]


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
    """
    Snapshot of the currently active frame in the UI.

    This is intentionally generic: the payload is exactly what we would send
    to the /generate endpoint as a frame JSON.
    """

    frame_slug: Optional[str] = Field(
        None,
        description="UI-facing identifier of the active frame (e.g. 'bio', 'timeline').",
        examples=["bio", "entity.organization", "event.election"],
    )
    frame_type: Optional[str] = Field(
        None,
        description=(
            "Canonical NLG frame_type discriminator, if known. "
            "If omitted, the backend may infer it from the payload."
        ),
        examples=["bio", "entity.organization", "event.election"],
    )
    payload: JSONDict = Field(
        default_factory=dict,
        description="Current frame JSON payload as it would be sent to /generate.",
    )


class AIGenerationContext(BaseModel):
    """
    Context about the latest NLG generation shown to the user.

    The assistant can use this to explain outputs, propose edits, etc.
    """

    lang: Optional[str] = Field(
        None,
        description="Language code used for the last /generate call, if any.",
        examples=["en", "fr", "sw"],
    )
    text: Optional[str] = Field(
        None,
        description="Last generated surface text that the user sees.",
    )
    debug_info: JSONDict = Field(
        default_factory=dict,
        description=(
            "Optional debug/metadata object returned alongside the last generation "
            "(e.g. engine IDs, constructions, traces)."
        ),
    )


class AIUserProfile(BaseModel):
    """
    Lightweight, optional hints about the human behind the session.

    This is deliberately coarse; it is *not* an identity model.
    """

    role: Optional[str] = Field(
        None,
        description="Free-form description of the user role (e.g. 'linguist', 'editor').",
    )
    experience_level: Optional[str] = Field(
        None,
        description="Free-form experience level (e.g. 'beginner', 'advanced').",
    )
    locale: Optional[str] = Field(
        None,
        description="UI locale (may differ from generation lang).",
        examples=["en-US", "fr-FR"],
    )
    extra: JSONDict = Field(
        default_factory=dict,
        description="Free-form metadata for future extensions.",
    )


class AIConversationMessage(BaseModel):
    """
    Single message in the side-panel conversation.

    The panel can choose to send a short history so the backend has context.
    """

    role: str = Field(
        ...,
        description="Conversation role; currently 'user' or 'assistant'.",
        pattern=r"^(user|assistant)$",
    )
    content: str = Field(
        ...,
        description="Plain-text content of the message.",
    )


class AIAssistRequest(BaseModel):
    """
    Main request shape for the /ai/assist endpoint.

    This is the generic entry point used by the AIPanel in the frontend.
    """

    user_query: str = Field(
        ...,
        description="Raw natural-language question or instruction from the user.",
    )
    lang: Optional[str] = Field(
        None,
        description=(
            "Preferred language for the assistant's reply. "
            "If omitted, the backend may default to the frame or UI language."
        ),
        examples=["en", "fr", "sw"],
    )
    frame: Optional[AIFrameContext] = Field(
        None,
        description="Snapshot of the currently active frame (if any).",
    )
    last_generation: Optional[AIGenerationContext] = Field(
        None,
        description="Information about the most recent NLG output, if available.",
    )
    user: Optional[AIUserProfile] = Field(
        None,
        description="Optional coarse-grained profile of the current user.",
    )
    conversation: List[AIConversationMessage] = Field(
        default_factory=list,
        description=(
            "Optional short conversation history between the user and the AI helper "
            "for this panel. The newest message should correspond to user_query."
        ),
    )
    extra: JSONDict = Field(
        default_factory=dict,
        description="Free-form bag for experiment flags, feature toggles, etc.",
    )


class AISuggestion(BaseModel):
    """
    Structured suggestion emitted by the AI assistant.

    The frontend can render these as cards and optionally allow the user
    to apply frame patches directly.
    """

    id: str = Field(
        ...,
        description="Opaque suggestion identifier (stable within a single response).",
    )
    kind: AISuggestionKind = Field(
        ...,
        description="Coarse category of the suggestion, used for UI rendering.",
    )
    title: str = Field(
        ...,
        description="Short title for the suggestion card.",
    )
    body: str = Field(
        ...,
        description="Main explanatory text for the suggestion (markdown-safe).",
    )
    score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional confidence / relevance score in [0, 1].",
    )
    highlight_fields: List[str] = Field(
        default_factory=list,
        description="Names of frame fields that this suggestion is most relevant to.",
    )
    frame_patch: JSONDict = Field(
        default_factory=dict,
        description=(
            "Partial frame payload that can be merged into the active frame "
            "if the user chooses to apply the suggestion."
        ),
    )
    follow_up_question: Optional[str] = Field(
        None,
        description="Optional follow-up question the assistant proposes.",
    )
    follow_up_hints: List[str] = Field(
        default_factory=list,
        description="Optional list of short follow-up prompts the user can click.",
    )


class AIQuickAction(BaseModel):
    """
    Pre-baked quick action that the UI can show as buttons or menu items.

    Examples:
    - 'Create a biography frame from this description'
    - 'Explain this output'
    """

    id: str = Field(
        ...,
        description="Stable identifier for the quick action.",
    )
    label: str = Field(
        ...,
        description="Short label shown on the button.",
    )
    description: Optional[str] = Field(
        None,
        description="Optional longer description (tooltip / menu text).",
    )
    frame_slug: Optional[str] = Field(
        None,
        description="If set, selects a frame in the UI when the action is triggered.",
    )
    initial_frame_payload: JSONDict = Field(
        default_factory=dict,
        description="Optional initial payload to seed the selected frame with.",
    )
    extra: JSONDict = Field(
        default_factory=dict,
        description="Free-form metadata for the frontend.",
    )


class AIAssistResponse(BaseModel):
    """
    Response shape for the /ai/assist endpoint.

    This is deliberately generic so it can cover:
    - inline chat-style replies,
    - structured suggestions,
    - one-click quick actions.
    """

    assistant_reply: str = Field(
        ...,
        description="Primary textual reply from the assistant (markdown-safe).",
    )
    suggestions: List[AISuggestion] = Field(
        default_factory=list,
        description="Zero or more structured suggestions related to the query.",
    )
    quick_actions: List[AIQuickAction] = Field(
        default_factory=list,
        description="Optional set of quick actions the UI can expose.",
    )
    conversation: List[AIConversationMessage] = Field(
        default_factory=list,
        description=(
            "Optional updated conversation history that the caller can store; "
            "may include the assistant's reply as the last message."
        ),
    )
    debug_info: JSONDict = Field(
        default_factory=dict,
        description="Opaque debug / tracing information for logs and diagnostics.",
    )
