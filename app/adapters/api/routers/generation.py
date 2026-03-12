# app/adapters/api/routers/generation.py
from typing import Any, Callable, Dict, NoReturn, Optional, Tuple, Union

import structlog
from fastapi import APIRouter, Body, Depends, Header, HTTPException, status

from app.adapters.api.contracts.generation_request_mapper import (
    map_generation_request,
    map_generation_request_from_payload,
)
from app.adapters.api.contracts.generation_response_mapper import (
    map_generation_response,
)
from app.adapters.api.dependencies import get_generate_text_use_case, verify_api_key
from app.adapters.redis_bus import redis_bus
from app.core.domain.context import DiscourseEntity
from app.core.domain.exceptions import (
    DomainError,
    InvalidFrameError,
    LanguageNotFoundError,
    UnsupportedFrameTypeError,
)
from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame, Sentence
from app.core.use_cases.generate_text import GenerateText

logger = structlog.get_logger()

router = APIRouter(
    prefix="/generate",
    tags=["Generation"],
    dependencies=[Depends(verify_api_key)],
)

GenerationFrame = Union[BioFrame, Frame]
ResolvedGenerationRequest = Tuple[str, GenerationFrame]


@router.post(
    "",
    response_model=Sentence,
    status_code=status.HTTP_200_OK,
    summary="Generate Text (language in payload)",
)
async def generate_text_from_payload(
    payload: Dict[str, Any] = Body(
        ...,
        description=(
            "Abstract Semantic Frame or Ninai Protocol payload "
            "(must include lang or inputs.language)"
        ),
    ),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    use_case: GenerateText = Depends(get_generate_text_use_case),
) -> Sentence:
    """
    Same generator, but language is provided inside the payload:
      - top-level: lang | language | lang_code
      - or inside inputs: language | lang | lang_code
    """
    return await _execute_generation(
        request_mapper=lambda: map_generation_request_from_payload(payload),
        x_session_id=x_session_id,
        use_case=use_case,
        log_lang=None,
    )


@router.post(
    "/{lang_code}",
    response_model=Sentence,
    status_code=status.HTTP_200_OK,
    summary="Generate Text from Abstract Frame",
)
async def generate_text(
    lang_code: str,
    payload: Dict[str, Any] = Body(
        ...,
        description="Abstract Semantic Frame or Ninai Protocol payload",
    ),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    use_case: GenerateText = Depends(get_generate_text_use_case),
) -> Sentence:
    """
    Converts a semantic frame into a concrete sentence in the target language.

    Features:
    - Ninai Protocol support via request mapping
    - Discourse planning via X-Session-ID
    - Domain validation via the use case
    """
    return await _execute_generation(
        request_mapper=lambda: map_generation_request(lang_code, payload),
        x_session_id=x_session_id,
        use_case=use_case,
        log_lang=lang_code,
    )


async def _execute_generation(
    *,
    request_mapper: Callable[[], ResolvedGenerationRequest],
    x_session_id: Optional[str],
    use_case: GenerateText,
    log_lang: Optional[str],
) -> Sentence:
    lang: Optional[str] = log_lang

    try:
        lang, frame = request_mapper()

        if x_session_id and isinstance(frame, BioFrame):
            await _apply_discourse_context(x_session_id, frame)

        sentence = await use_case.execute(lang, frame)
        return map_generation_response(sentence)

    except Exception as exc:
        _raise_generation_http_exception(exc, lang=lang)


def _raise_generation_http_exception(exc: Exception, *, lang: Optional[str]) -> NoReturn:
    if isinstance(exc, (InvalidFrameError, UnsupportedFrameTypeError, ValueError)):
        logger.warning("generation_bad_request", lang=lang, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    if isinstance(exc, LanguageNotFoundError):
        logger.warning("generation_language_not_found", lang=lang, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(exc, DomainError):
        logger.error("generation_domain_error", lang=lang, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generation failed: {str(exc)}",
        )

    logger.critical("unexpected_generation_crash", lang=lang, error=str(exc), exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred during text generation.",
    )


def _extract_subject_qid(frame: BioFrame) -> Optional[str]:
    """
    Best-effort extraction of the entity identifier used for discourse focus.
    """
    subj = getattr(frame, "subject", None)
    if isinstance(subj, dict):
        qid = subj.get("qid")
        if isinstance(qid, str) and qid.strip():
            return qid.strip()
        return None

    if subj is not None:
        qid = getattr(subj, "qid", None)
        if isinstance(qid, str) and qid.strip():
            return qid.strip()

    qid = getattr(frame, "qid", None)
    if isinstance(qid, str) and qid.strip():
        return qid.strip()

    return None


async def _apply_discourse_context(session_id: str, frame: BioFrame) -> None:
    """
    Applies pronominalization logic based on the session history.
    Mutates the frame in-place if the subject matches the current focus.
    """
    context = await redis_bus.get_session(session_id)
    if context is None:
        return

    subject_qid = _extract_subject_qid(frame)
    if not subject_qid:
        return

    original_label = getattr(frame, "name", None)

    if context.current_focus and context.current_focus.qid == subject_qid:
        logger.info("pronominalization_triggered", session=session_id)

        if frame.meta is None:
            frame.meta = {}

        gender_map = {
            "f": ("She", "she_Pron"),
            "female": ("She", "she_Pron"),
            "m": ("He", "he_Pron"),
            "male": ("He", "he_Pron"),
            "n": ("It", "it_Pron"),
            "neuter": ("It", "it_Pron"),
        }

        focus_gender = getattr(context.current_focus, "gender", None)
        pronoun_label, gf_arg = gender_map.get(
            str(focus_gender or "").strip().lower(),
            ("It", "it_Pron"),
        )

        frame.name = pronoun_label
        frame.meta["gf_function"] = "UsePron"
        frame.meta["gf_arg"] = gf_arg

        focus_label = (
            getattr(context.current_focus, "label", None)
            or original_label
            or pronoun_label
        )
        focus_qid = getattr(context.current_focus, "qid", None) or subject_qid
        focus_gender_out = focus_gender or (getattr(frame, "gender", None) or "n")
    else:
        focus_label = original_label or getattr(frame, "name", None) or "It"
        focus_qid = subject_qid
        focus_gender_out = getattr(frame, "gender", None) or "n"

    new_entity = DiscourseEntity(
        label=focus_label,
        gender=focus_gender_out,
        qid=focus_qid,
        recency=0,
    )
    context.update_focus(new_entity)
    await redis_bus.save_session(context)