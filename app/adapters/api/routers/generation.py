# app/adapters/api/routers/generation.py
from typing import Any, Dict, Optional, Union

import structlog
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status

# Core Domain Imports
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

# Adapters & Infrastructure
from app.adapters.api.dependencies import get_generate_text_use_case, verify_api_key
from app.adapters.ninai import ninai_adapter
from app.adapters.redis_bus import redis_bus

# Shared
from app.shared.lexicon import lexicon

logger = structlog.get_logger()

router = APIRouter(
    prefix="/generate",
    tags=["Generation"],
    dependencies=[Depends(verify_api_key)],
)

_BIOISH_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}


@router.post(
    "",
    response_model=Sentence,
    status_code=status.HTTP_200_OK,
    summary="Generate Text (language in payload)",
)
async def generate_text_from_payload(
    request: Request,
    payload: Dict[str, Any] = Body(
        ...,
        description="Abstract Semantic Frame or Ninai Protocol payload (must include lang or inputs.language)",
    ),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    use_case: GenerateText = Depends(get_generate_text_use_case),
):
    """
    Same generator, but language is provided inside the payload:
      - top-level: lang | language | lang_code
      - or inside inputs: language | lang | lang_code

    This matches the GUI Dynamic Test Bench request shape.
    """
    _ = request
    lang_raw: Optional[str] = None

    try:
        lang_raw = _extract_lang_from_payload(payload)
        if not lang_raw:
            raise InvalidFrameError(
                "Missing language. Provide `lang` (top-level) or `inputs.language`."
            )

        lang = _normalize_lang_code(lang_raw)
        cleaned_payload = _strip_lang_fields(payload)

        frame = _parse_payload(cleaned_payload, lang)

        if x_session_id and isinstance(frame, BioFrame):
            await _apply_discourse_context(x_session_id, frame)

        sentence = await use_case.execute(lang, frame)
        return sentence

    except (InvalidFrameError, UnsupportedFrameTypeError, ValueError) as e:
        logger.warning("generation_bad_request", lang=lang_raw, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except LanguageNotFoundError as e:
        logger.warning("generation_language_not_found", lang=lang_raw, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DomainError as e:
        logger.error("generation_domain_error", lang=lang_raw, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generation failed: {str(e)}",
        )
    except Exception as e:
        logger.critical("unexpected_generation_crash", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during text generation.",
        )


@router.post(
    "/{lang_code}",
    response_model=Sentence,
    status_code=status.HTTP_200_OK,
    summary="Generate Text from Abstract Frame",
)
async def generate_text(
    request: Request,
    lang_code: str,
    payload: Dict[str, Any] = Body(
        ...,
        description="Abstract Semantic Frame or Ninai Protocol payload",
    ),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    use_case: GenerateText = Depends(get_generate_text_use_case),
):
    """
    Converts a Semantic Frame (abstract intent) into a concrete Sentence in the target language.

    Features:
    - Ninai Protocol Support: Auto-detects and parses recursive Ninai object trees.
    - Discourse Planning: Handles pronominalization context via X-Session-ID.
    - Validation: Enforces domain constraints via the Use Case.
    """
    _ = request
    lang = _normalize_lang_code(lang_code)

    try:
        payload_lang_raw = _extract_lang_from_payload(payload)
        if payload_lang_raw:
            payload_lang = _normalize_lang_code(payload_lang_raw)
            if payload_lang != lang:
                raise InvalidFrameError(
                    f"Language mismatch: URL has '{lang_code}' -> '{lang}', "
                    f"payload has '{payload_lang_raw}' -> '{payload_lang}'."
                )

        cleaned_payload = _strip_lang_fields(payload)

        frame = _parse_payload(cleaned_payload, lang)

        if x_session_id and isinstance(frame, BioFrame):
            await _apply_discourse_context(x_session_id, frame)

        sentence = await use_case.execute(lang, frame)
        return sentence

    except (InvalidFrameError, UnsupportedFrameTypeError, ValueError) as e:
        logger.warning("generation_bad_request", lang=lang, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except LanguageNotFoundError as e:
        logger.warning("generation_language_not_found", lang=lang, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except DomainError as e:
        logger.error("generation_domain_error", lang=lang, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Generation failed: {str(e)}",
        )
    except Exception as e:
        logger.critical("unexpected_generation_crash", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during text generation.",
        )


def _normalize_lang_code(lang_code: str) -> str:
    """
    Normalizes common lang-code variants without assuming ISO2 vs ISO3.

    - trims/lowers
    - strips a leading 'wiki' prefix if present (e.g., 'wikieng' -> 'eng')
    - maps ISO3/odd codes to ISO2 via lexicon.normalize_code (e.g., 'zul' -> 'zu')
    """
    code = (lang_code or "").strip().lower()
    if code.startswith("wiki") and len(code) > 4:
        code = code[4:]
    return lexicon.normalize_code(code)


def _extract_lang_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    for k in ("lang", "language", "lang_code"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    inputs = payload.get("inputs")
    if isinstance(inputs, dict):
        for k in ("language", "lang", "lang_code"):
            v = inputs.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    return None


def _strip_lang_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove language fields from the payload so they don't pollute Frame inputs
    (e.g., GF argument mismatch from an extra 'language' key).
    """
    if not isinstance(payload, dict):
        return payload

    cleaned = dict(payload)

    for k in ("lang", "language", "lang_code", "lang_name"):
        cleaned.pop(k, None)

    inputs = cleaned.get("inputs")
    if isinstance(inputs, dict):
        new_inputs = dict(inputs)
        for k in ("lang", "language", "lang_code"):
            new_inputs.pop(k, None)
        cleaned["inputs"] = new_inputs

    return cleaned


def _is_non_empty_scalar(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _is_bioish_frame_type(frame_type: Any) -> bool:
    ft = str(frame_type or "").strip().lower()
    return ft in _BIOISH_FRAME_TYPES or (ft.startswith("entity.") and "person" in ft)


def _coerce_bio_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accept both canonical BioFrame payloads and flat GUI/test-bench person payloads.

    Supported inputs:
      - canonical:
          {"frame_type":"bio","subject":{"name":"Alan Turing", ...}}
      - flat:
          {"frame_type":"entity.person","name":"Alan Turing","profession":"Mathematician", ...}
      - mixed:
          {"frame_type":"bio","subject":{"name":"Alan Turing"},"profession":"Mathematician"}
      - inputs-wrapped:
          {"frame_type":"entity.person","inputs":{"name":"Alan Turing", ...}}
    """
    if not isinstance(payload, dict):
        raise InvalidFrameError("Payload must be a JSON object.")

    normalized = dict(payload)
    inputs = normalized.get("inputs")
    properties = normalized.get("properties")

    subject: Dict[str, Any] = {}

    if isinstance(inputs, dict):
        inputs_subject = inputs.get("subject")
        if isinstance(inputs_subject, dict):
            subject.update(inputs_subject)

    raw_subject = normalized.get("subject")
    if isinstance(raw_subject, dict):
        subject.update(raw_subject)

    def _fill_from(source: Any, source_key: str, subject_key: str) -> None:
        if not isinstance(source, dict):
            return
        value = source.get(source_key)
        if _is_non_empty_scalar(value) and not _is_non_empty_scalar(subject.get(subject_key)):
            subject[subject_key] = value

    for source in (inputs, normalized, properties):
        _fill_from(source, "name", "name")
        _fill_from(source, "label", "name")
        _fill_from(source, "profession", "profession")
        _fill_from(source, "occupation", "profession")
        _fill_from(source, "nationality", "nationality")
        _fill_from(source, "citizenship", "nationality")
        _fill_from(source, "gender", "gender")
        _fill_from(source, "sex", "gender")
        _fill_from(source, "qid", "qid")

    if not _is_non_empty_scalar(subject.get("name")):
        raise InvalidFrameError(
            "Bio/person payload requires a subject name. "
            "Provide `subject.name` or top-level `name`/`label`."
        )

    normalized["frame_type"] = "bio"
    normalized["subject"] = subject
    return normalized


def _parse_payload(payload: Dict[str, Any], lang_code: str) -> Union[BioFrame, Frame]:
    """
    Determines if the payload is Ninai Protocol or a standard Frame
    and converts it to the appropriate Domain Entity.
    """
    if not isinstance(payload, dict):
        raise InvalidFrameError("Payload must be a JSON object.")

    if "function" in payload:
        logger.info("ninai_protocol_detected", lang=lang_code)
        try:
            return ninai_adapter.parse(payload)
        except ValueError as e:
            raise InvalidFrameError(f"Ninai Parsing Error: {str(e)}") from e

    frame_type = payload.get("frame_type")
    if not frame_type:
        raise InvalidFrameError("Missing required field: frame_type")

    try:
        if _is_bioish_frame_type(frame_type):
            normalized = _coerce_bio_payload(payload)
            logger.info(
                "bio_payload_normalized",
                lang=lang_code,
                original_frame_type=str(frame_type),
                subject_keys=sorted(normalized["subject"].keys()),
            )
            return BioFrame(**normalized)

        return Frame(**payload)

    except InvalidFrameError:
        raise
    except Exception as e:
        raise InvalidFrameError(f"Invalid Frame format: {str(e)}") from e


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
        pronoun_label, gf_arg = gender_map.get(str(focus_gender or "").strip().lower(), ("It", "it_Pron"))

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