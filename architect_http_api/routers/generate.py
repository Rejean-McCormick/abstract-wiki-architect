# architect_http_api/routers/generate.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nlg.api import GenerationOptions, NLGSession
from semantics.aw_bridge import UnknownFrameTypeError, frame_from_aw
from semantics.all_frames import frame_to_dict
from utils.logging_setup import get_logger

log = get_logger(__name__)

router = APIRouter(
    prefix="/generate",
    tags=["generate"],
)


# ---------------------------------------------------------------------------
# Pydantic models (HTTP payloads)
# ---------------------------------------------------------------------------


class GenerationOptionsPayload(BaseModel):
    """
    HTTP-facing representation of GenerationOptions.

    This is intentionally a thin mirror of nlg.api.GenerationOptions.
    """

    register: Optional[str] = Field(
        default=None,
        description='Style register, e.g. "neutral", "formal", "informal".',
    )
    max_sentences: Optional[int] = Field(
        default=None,
        ge=1,
        description="Upper bound on number of sentences to generate.",
    )
    discourse_mode: Optional[str] = Field(
        default=None,
        description='High-level discourse mode, e.g. "intro", "summary".',
    )
    seed: Optional[int] = Field(
        default=None,
        description="Reserved for future stochastic behavior.",
    )

    def to_generation_options(self) -> GenerationOptions:
        """
        Convert the HTTP payload into the internal GenerationOptions dataclass.
        """
        return GenerationOptions(
            register=self.register,
            max_sentences=self.max_sentences,
            discourse_mode=self.discourse_mode,
            seed=self.seed,
        )


class GenerateRequest(BaseModel):
    """
    Request body for /generate.

    The `frame` field is an AbstractWiki-style JSON payload; it is converted to
    a semantic Frame via semantics.aw_bridge.frame_from_aw.
    """

    lang: str = Field(
        ...,
        description="Target language code (e.g. 'en', 'fr', 'sw').",
    )
    frame: Dict[str, Any] = Field(
        ...,
        description=(
            "AbstractWiki-style frame payload. "
            "Must contain enough information to infer a canonical frame_type; "
            "see docs/FRAMES_*.md and semantics.aw_bridge."
        ),
    )
    options: Optional[GenerationOptionsPayload] = Field(
        default=None,
        description="Optional generation controls (style, length, discourse mode).",
    )
    debug: bool = Field(
        default=False,
        description="If true, include debug_info from the underlying engine (when available).",
    )


class GenerateResponse(BaseModel):
    """
    Standard HTTP response for /generate.

    Note: `frame` is returned as a canonical dictionary via frame_to_dict,
    which may differ from the raw input payload (normalization, defaults, etc.).
    """

    text: str
    sentences: List[str]
    lang: str
    frame: Dict[str, Any]
    debug_info: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

# Single shared NLG session for this process. If you want to preload languages,
# adjust the constructor call here.
_SESSION = NLGSession()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GenerateResponse,
    summary="Generate text from a semantic frame",
)
def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Main HTTP entry point: AbstractWiki-style frame → realized text.

    Steps:
    1. Normalize the incoming AW payload into a semantic Frame.
    2. Call NLGSession.generate with the requested language and options.
    3. Convert the internal Frame back to a canonical dict for the response.
    """
    frame_type = str(req.frame.get("frame_type", "")).strip() or None
    log.info(
        "HTTP /generate request: lang=%s frame_type=%s debug=%s",
        req.lang,
        frame_type,
        req.debug,
    )

    try:
        frame = frame_from_aw(req.frame)
    except UnknownFrameTypeError as exc:
        log.warning(
            "Unknown or unsupported frame_type in /generate payload",
            extra={"frame_type": exc.frame_type},
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "unknown_frame_type",
                "message": str(exc),
                "frame_type": exc.frame_type,
            },
        ) from exc
    except Exception as exc:
        log.exception("Error while normalizing AW payload in /generate")
        raise HTTPException(
            status_code=500,
            detail="Internal error while normalizing frame payload.",
        ) from exc

    options = req.options.to_generation_options() if req.options else None

    try:
        result = _SESSION.generate(
            lang=req.lang,
            frame=frame,
            options=options,
            debug=req.debug,
        )
    except Exception as exc:
        log.exception("Error during NLGSession.generate in /generate")
        raise HTTPException(
            status_code=500,
            detail="Internal error while generating text.",
        ) from exc

    # Convert internal frame back to a canonical dictionary form.
    normalized_frame = frame_to_dict(result.frame)

    return GenerateResponse(
        text=result.text,
        sentences=result.sentences,
        lang=result.lang,
        frame=normalized_frame,
        debug_info=result.debug_info,
    )
