from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from architect_http_api.services.ai_client import AiClient
from architect_http_api.ai.intent_handler import IntentHandler
from architect_http_api.ai.suggestions import SuggestionsEngine
from architect_http_api.ai.explanations import ExplanationEngine
from architect_http_api.schemas.ai import (
    AIIntentRequest,
    AIIntentResponse,
    AISuggestFieldsRequest,
    AISuggestFieldsResponse,
    AIExplainRequest,
    AIExplainResponse,
)
from architect_http_api.schemas.common import ErrorResponse

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
)


# ---------------------------------------------------------------------------
# Dependency wiring
# ---------------------------------------------------------------------------


def get_ai_client() -> AiClient:
    """
    Factory for the low-level LLM / AI client.

    The AiClient itself is responsible for reading configuration (API keys,
    model names, timeouts, etc.) from environment variables or settings.
    """
    return AiClient()


def get_intent_handler(ai_client: AiClient = Depends(get_ai_client)) -> IntentHandler:
    """
    High-level helper that turns a free-form user utterance into a
    structured intent for the UI (which frame, which mode, etc.).
    """
    return IntentHandler(ai_client=ai_client)


def get_suggestions_engine(
    ai_client: AiClient = Depends(get_ai_client),
) -> SuggestionsEngine:
    """
    Engine that proposes field values / frame parameters given:
    - a frame type,
    - partial data,
    - and optional free-text instructions.
    """
    return SuggestionsEngine(ai_client=ai_client)


def get_explanation_engine(
    ai_client: AiClient = Depends(get_ai_client),
) -> ExplanationEngine:
    """
    Engine that explains why a given field / frame choice is reasonable
    in plain language (for FieldInspector / debug / pedagogy).
    """
    return ExplanationEngine(ai_client=ai_client)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/intent",
    response_model=AIIntentResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def infer_intent(
    payload: AIIntentRequest,
    handler: IntentHandler = Depends(get_intent_handler),
) -> AIIntentResponse:
    """
    Infer the user's high-level intent from a natural-language instruction.

    Typical usage in the frontend:
    - AIPanel sends the latest user message + current frame context.
    - Backend returns:
        * which frame type(s) seem relevant,
        * whether this is “create a new frame”, “edit current frame”, etc.,
        * optional suggested slug / title,
        * natural-language rationale.
    """
    try:
        intent = await handler.infer_intent(payload)
    except ValueError as exc:
        # Semantic / validation error in the request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI intent inference failed",
        ) from exc

    return intent


@router.post(
    "/suggest-fields",
    response_model=AISuggestFieldsResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def suggest_fields(
    payload: AISuggestFieldsRequest,
    engine: SuggestionsEngine = Depends(get_suggestions_engine),
) -> AISuggestFieldsResponse:
    """
    Suggest concrete field values for a frame.

    Typical usage:
    - User picks an entity / topic and a frame type (e.g. PERSON, EVENT).
    - AIPanel sends:
        * frame_type,
        * any existing field values,
        * optional free-text hint (“focus on awards and offices”).
    - Backend returns a list of suggested fields with values + rationales.
    """
    try:
        suggestions = await engine.suggest_fields(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI field suggestion failed",
        ) from exc

    return suggestions


@router.post(
    "/explain-field",
    response_model=AIExplainResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def explain_field(
    payload: AIExplainRequest,
    engine: ExplanationEngine = Depends(get_explanation_engine),
) -> AIExplainResponse:
    """
    Produce a human-readable explanation for a given field or frame choice.

    Frontend usage:
    - FieldInspector sends:
        * frame_type,
        * field_name / value,
        * optional global context (entity label, language, etc.).
    - Backend returns a short explanation and, optionally, a title.
    """
    try:
        explanation = await engine.explain_field(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - safety net
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI explanation generation failed",
        ) from exc

    return explanation
