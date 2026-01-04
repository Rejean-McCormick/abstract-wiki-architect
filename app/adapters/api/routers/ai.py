# app/adapters/api/routers/ai.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = structlog.get_logger()

router = APIRouter(prefix="/ai", tags=["AI"])


# ----------------------------
# DTOs
# ----------------------------

class SuggestionRequest(BaseModel):
    utterance: str = Field(..., min_length=1, description="User natural-language request")
    lang: Optional[str] = Field(default="en", description="Language code (e.g., 'en')")


class SuggestionOut(BaseModel):
    frame_type: str
    title: str
    description: str
    confidence: Optional[float] = None


class SuggestionResponse(BaseModel):
    suggestions: List[SuggestionOut]


class IntentRequest(BaseModel):
    utterance: str = Field(..., min_length=1)
    lang: Optional[str] = "en"
    context: Optional[Dict[str, Any]] = None


class IntentResponse(BaseModel):
    intent: str
    patches: List[Dict[str, Any]] = Field(default_factory=list)
    assistant_messages: List[Dict[str, str]] = Field(default_factory=list)


# ----------------------------
# Helpers
# ----------------------------

def _heuristic_suggestions(text: str) -> List[SuggestionOut]:
    t = (text or "").strip().lower()

    suggestions: List[SuggestionOut] = []

    # Very simple heuristics (kept deterministic for tests)
    if any(k in t for k in ["who is", "who was", "biography", "bio", "life of"]):
        suggestions.append(
            SuggestionOut(
                frame_type="bio",
                title="Biography",
                description="Generate a short biography for the subject mentioned.",
                confidence=0.75,
            )
        )

    if any(k in t for k in ["timeline", "history", "chronology", "events"]):
        suggestions.append(
            SuggestionOut(
                frame_type="timeline",
                title="Timeline",
                description="Generate a timeline of key events related to the subject.",
                confidence=0.65,
            )
        )

    if any(k in t for k in ["define", "definition", "what is", "meaning"]):
        suggestions.append(
            SuggestionOut(
                frame_type="definition",
                title="Definition",
                description="Generate a concise definition/explanation for the term.",
                confidence=0.70,
            )
        )

    # Always return at least one suggestion (required by tests)
    if not suggestions:
        suggestions.append(
            SuggestionOut(
                frame_type="bio",
                title="Biography (default)",
                description="Generate a short biography for the main subject in the request.",
                confidence=0.55,
            )
        )

    return suggestions


# ----------------------------
# Endpoints
# ----------------------------

@router.post("/suggestions", response_model=SuggestionResponse)
async def ai_suggestions(payload: SuggestionRequest) -> SuggestionResponse:
    """
    Returns candidate frames the user likely wants to generate.
    Contract (tests): response has {"suggestions": [...]} and each item contains:
      - frame_type
      - title
      - description
    """
    suggestions = _heuristic_suggestions(payload.utterance)
    return SuggestionResponse(suggestions=suggestions)


@router.post("/intent", response_model=IntentResponse)
async def process_intent(payload: IntentRequest) -> IntentResponse:
    """
    Light-weight intent parsing endpoint for the UI.
    Currently heuristic/stubbed: returns an intent label and optional patches.
    """
    text = (payload.utterance or "").strip()
    if not text:
        return IntentResponse(intent="unknown")

    # Minimal heuristic intent label
    intent = "suggest_frames"
    if any(k in text.lower() for k in ["who is", "who was", "biography", "bio"]):
        intent = "create_bio"

    return IntentResponse(
        intent=intent,
        patches=[],
        assistant_messages=[
            {"role": "assistant", "content": "Intent processed (heuristic)."}
        ],
    )
