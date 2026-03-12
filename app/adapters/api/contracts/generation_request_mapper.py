from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Union

import structlog

from app.adapters.ninai import ninai_adapter
from app.core.domain.exceptions import InvalidFrameError
from app.core.domain.frame import BioFrame
from app.core.domain.models import Frame
from app.shared.lexicon import lexicon

logger = structlog.get_logger()

_BIOISH_FRAME_TYPES = {
    "bio",
    "biography",
    "entity.person",
    "entity_person",
    "person",
    "entity.person.v1",
    "entity.person.v2",
}


@dataclass(frozen=True, slots=True)
class MappedGenerationRequest:
    """
    HTTP-to-domain generation request envelope.

    The router can depend on this mapper to:
    - resolve the authoritative language code,
    - strip transport-only language fields from the payload,
    - normalize bio/person payload variants,
    - parse Ninai or standard frame payloads into domain objects.
    """

    lang_code: str
    frame: Union[BioFrame, Frame]
    payload: Dict[str, Any]


def map_generation_request(
    payload: Mapping[str, Any],
    *,
    path_lang_code: Optional[str] = None,
) -> MappedGenerationRequest:
    """
    Convert an API payload into a normalized generation command.

    Rules:
    - If `path_lang_code` is provided, it is authoritative.
    - If both URL and payload languages are provided, they must match after normalization.
    - If no URL language is provided, the payload must contain one.
    """
    if not isinstance(payload, Mapping):
        raise InvalidFrameError("Payload must be a JSON object.")

    raw_payload = dict(payload)
    payload_lang_raw = extract_lang_from_payload(raw_payload)

    if path_lang_code:
        lang_code = normalize_lang_code(path_lang_code)

        if payload_lang_raw:
            payload_lang = normalize_lang_code(payload_lang_raw)
            if payload_lang != lang_code:
                raise InvalidFrameError(
                    f"Language mismatch: URL has '{path_lang_code}' -> '{lang_code}', "
                    f"payload has '{payload_lang_raw}' -> '{payload_lang}'."
                )
    else:
        if not payload_lang_raw:
            raise InvalidFrameError(
                "Missing language. Provide `lang` (top-level) or `inputs.language`."
            )
        lang_code = normalize_lang_code(payload_lang_raw)

    cleaned_payload = strip_lang_fields(raw_payload)
    frame = parse_generation_payload(cleaned_payload, lang_code)

    return MappedGenerationRequest(
        lang_code=lang_code,
        frame=frame,
        payload=cleaned_payload,
    )


def normalize_lang_code(lang_code: str) -> str:
    """
    Normalize common language-code variants without assuming a fixed width.

    Current behavior mirrors the generation router:
    - trims and lowercases,
    - strips a leading `wiki` prefix if present,
    - delegates canonicalization to `lexicon.normalize_code`.
    """
    code = (lang_code or "").strip().lower()
    if code.startswith("wiki") and len(code) > 4:
        code = code[4:]
    return lexicon.normalize_code(code)


def extract_lang_from_payload(payload: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(payload, Mapping):
        return None

    for key in ("lang", "language", "lang_code"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    inputs = payload.get("inputs")
    if isinstance(inputs, Mapping):
        for key in ("language", "lang", "lang_code"):
            value = inputs.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def strip_lang_fields(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Remove transport-level language keys so they do not leak into frame parsing.
    """
    if not isinstance(payload, Mapping):
        raise InvalidFrameError("Payload must be a JSON object.")

    cleaned = dict(payload)

    for key in ("lang", "language", "lang_code", "lang_name"):
        cleaned.pop(key, None)

    inputs = cleaned.get("inputs")
    if isinstance(inputs, Mapping):
        new_inputs = dict(inputs)
        for key in ("lang", "language", "lang_code"):
            new_inputs.pop(key, None)
        cleaned["inputs"] = new_inputs

    return cleaned


def parse_generation_payload(payload: Mapping[str, Any], lang_code: str) -> Union[BioFrame, Frame]:
    """
    Parse a normalized request payload into the domain frame expected by GenerateText.
    """
    if not isinstance(payload, Mapping):
        raise InvalidFrameError("Payload must be a JSON object.")

    payload_dict = dict(payload)

    if "function" in payload_dict:
        logger.info("ninai_protocol_detected", lang=lang_code)
        try:
            return ninai_adapter.parse(payload_dict)
        except ValueError as exc:
            raise InvalidFrameError(f"Ninai Parsing Error: {str(exc)}") from exc

    frame_type = payload_dict.get("frame_type")
    if not frame_type:
        raise InvalidFrameError("Missing required field: frame_type")

    try:
        if is_bioish_frame_type(frame_type):
            normalized = coerce_bio_payload(payload_dict)
            logger.info(
                "bio_payload_normalized",
                lang=lang_code,
                original_frame_type=str(frame_type),
                subject_keys=sorted(normalized["subject"].keys()),
            )
            return BioFrame(**normalized)

        return Frame(**payload_dict)
    except InvalidFrameError:
        raise
    except Exception as exc:
        raise InvalidFrameError(f"Invalid Frame format: {str(exc)}") from exc


def is_bioish_frame_type(frame_type: Any) -> bool:
    ft = str(frame_type or "").strip().lower()
    return ft in _BIOISH_FRAME_TYPES or (ft.startswith("entity.") and "person" in ft)


def coerce_bio_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Accept both canonical BioFrame payloads and flat GUI/test-bench person payloads.

    Supported inputs:
      - canonical:
          {"frame_type": "bio", "subject": {"name": "Alan Turing", ...}}
      - flat:
          {"frame_type": "entity.person", "name": "Alan Turing", ...}
      - mixed:
          {"frame_type": "bio", "subject": {"name": "Alan Turing"}, "profession": "Mathematician"}
      - inputs-wrapped:
          {"frame_type": "entity.person", "inputs": {"name": "Alan Turing", ...}}
    """
    if not isinstance(payload, Mapping):
        raise InvalidFrameError("Payload must be a JSON object.")

    normalized = dict(payload)
    inputs = normalized.get("inputs")
    properties = normalized.get("properties")

    subject: Dict[str, Any] = {}

    if isinstance(inputs, Mapping):
        inputs_subject = inputs.get("subject")
        if isinstance(inputs_subject, Mapping):
            subject.update(dict(inputs_subject))

    raw_subject = normalized.get("subject")
    if isinstance(raw_subject, Mapping):
        subject.update(dict(raw_subject))

    def _fill_from(source: Any, source_key: str, subject_key: str) -> None:
        if not isinstance(source, Mapping):
            return
        value = source.get(source_key)
        if is_non_empty_scalar(value) and not is_non_empty_scalar(subject.get(subject_key)):
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

    if not is_non_empty_scalar(subject.get("name")):
        raise InvalidFrameError(
            "Bio/person payload requires a subject name. "
            "Provide `subject.name` or top-level `name`/`label`."
        )

    normalized["frame_type"] = "bio"
    normalized["subject"] = subject
    return normalized


def is_non_empty_scalar(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


__all__ = [
    "MappedGenerationRequest",
    "map_generation_request",
    "normalize_lang_code",
    "extract_lang_from_payload",
    "strip_lang_fields",
    "parse_generation_payload",
    "is_bioish_frame_type",
    "coerce_bio_payload",
]