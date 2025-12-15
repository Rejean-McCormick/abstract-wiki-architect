# semantics\normalization.py
"""
semantics/normalization.py
==========================

Light-weight helpers to turn "messy" abstract inputs into a clean,
predictable shape before they hit the engines / constructions.

This module focuses on:
1. Unwrapping Wikifunctions Z-objects.
2. Normalizing core biography semantics.
3. Constructing high-level Frame objects (BioFrame, Event, etc.) from dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

# Import Core Types for Frame construction
from semantics.types import (
    Entity,
    Location,
    TimeSpan,
    Event,
    BioFrame,
    Frame
)

try:
    # Preferred: use the project's Wikifunctions mock if available
    from utils.wikifunctions_api_mock import unwrap as _unwrap_zobject
except ImportError:  # pragma: no cover - defensive fallback for isolated use

    def _unwrap_zobject(obj: Any) -> Any:
        """
        Minimal fallback: return plain strings as-is, unwrap naive Z6/Z9 dicts,
        otherwise return the object unchanged.
        """
        if isinstance(obj, str):
            return obj
        if isinstance(obj, dict):
            t = obj.get("Z1K1")
            if t == "Z6":
                return obj.get("Z6K1", "")
            if t == "Z9":
                return obj.get("Z9K1", "")
        return obj


# ---------------------------------------------------------------------------
# Dataclasses used by callers
# ---------------------------------------------------------------------------


@dataclass
class BioSemantics:
    """
    Canonical semantic input for a simple encyclopedic biography sentence.
    """
    name: str
    gender: str
    profession_lemma: str
    nationality_lemma: str
    language: str
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InfoStructure:
    """Information-structure annotations for a single clause."""
    topic: List[str] = field(default_factory=list)
    focus: List[str] = field(default_factory=list)
    background: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Primitive normalizers
# ---------------------------------------------------------------------------


def _normalize_string(value: Any) -> str:
    value = _unwrap_zobject(value)
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _lower_ascii(value: Any) -> str:
    s = _normalize_string(value)
    return s.lower()


# ---------------------------------------------------------------------------
# Gender normalization
# ---------------------------------------------------------------------------

_WD_MALE = {"Q6581097"}
_WD_FEMALE = {"Q6581072"}
_WD_NONBINARY = {"Q48270", "Q1097630"}


def normalize_gender(raw: Any) -> str:
    if raw is None:
        return "unknown"

    unwrapped = _unwrap_zobject(raw)

    if isinstance(unwrapped, Mapping):
        qid = unwrapped.get("id") or unwrapped.get("wikidata_qid")
        if isinstance(qid, str):
            return normalize_gender(qid)

    token = _lower_ascii(unwrapped)

    if not token:
        return "unknown"

    if token in _WD_MALE: return "male"
    if token in _WD_FEMALE: return "female"
    if token in _WD_NONBINARY: return "nonbinary"

    if token in {"m", "male", "man", "masculine"}: return "male"
    if token in {"f", "female", "woman", "feminine"}: return "female"
    if token in {"nonbinary", "non-binary", "nb", "enby"}: return "nonbinary"
    if token in {"unknown", "unspecified", "na", "n/a", "none"}: return "unknown"

    return "other"


# ---------------------------------------------------------------------------
# Information-structure normalization
# ---------------------------------------------------------------------------


def _ensure_role_list(value: Any) -> List[str]:
    if value is None: return []
    value = _unwrap_zobject(value)
    if isinstance(value, str):
        v = value.strip()
        return [v] if v else []
    if isinstance(value, Mapping) and "role" in value:
        r = _normalize_string(value["role"])
        return [r] if r else []
    if isinstance(value, Sequence):
        out: List[str] = []
        for elem in value:
            s = _normalize_string(elem)
            if s: out.append(s)
        return out
    s = _normalize_string(value)
    return [s] if s else []


def normalize_info_structure(raw: Optional[Mapping[str, Any]]) -> InfoStructure:
    if not raw: return InfoStructure()
    topic_val = raw.get("topic") or raw.get("topic_role") or raw.get("topics") or raw.get("topic_roles")
    focus_val = raw.get("focus") or raw.get("focus_role") or raw.get("foci") or raw.get("focus_roles")
    background_val = raw.get("background") or raw.get("background_roles") or raw.get("given") or raw.get("given_roles")

    return InfoStructure(
        topic=_ensure_role_list(topic_val),
        focus=_ensure_role_list(focus_val),
        background=_ensure_role_list(background_val),
    )


# ---------------------------------------------------------------------------
# Biography semantics normalization
# ---------------------------------------------------------------------------


def normalize_bio_semantics(
    raw: Union[Mapping[str, Any], Sequence[Any]],
    *,
    default_lang: str = "en",
) -> BioSemantics:
    if isinstance(raw, Mapping):
        name = _normalize_string(raw.get("name") or raw.get("label") or raw.get("K1"))
        gender = normalize_gender(raw.get("gender") or raw.get("sex") or raw.get("K2"))
        prof_lemma = _normalize_string(raw.get("profession") or raw.get("occupation") or raw.get("prof_lemma") or raw.get("K3"))
        nat_lemma = _normalize_string(raw.get("nationality") or raw.get("citizenship") or raw.get("nat_lemma") or raw.get("K4"))
        lang_code = _lower_ascii(raw.get("language") or raw.get("lang") or raw.get("K5"))
        if not lang_code: lang_code = _lower_ascii(default_lang)

        extra: Dict[str, Any] = {}
        for k, v in raw.items():
            if k not in {"name", "label", "gender", "sex", "profession", "occupation", "prof_lemma", "nationality", "citizenship", "nat_lemma", "language", "lang", "K1", "K2", "K3", "K4", "K5"}:
                extra[k] = v

        return BioSemantics(name, gender, prof_lemma, nat_lemma, lang_code, extra)

    if isinstance(raw, Sequence):
        seq = list(raw)
        def _idx(i: int, d: Any = "") -> Any: return seq[i] if i < len(seq) else d
        return BioSemantics(
            name=_normalize_string(_idx(0)),
            gender=normalize_gender(_idx(1, None)),
            profession_lemma=_normalize_string(_idx(2)),
            nationality_lemma=_normalize_string(_idx(3)),
            language=_lower_ascii(_idx(4, default_lang)),
            extra={},
        )

    name = _normalize_string(raw)
    return BioSemantics(name, "unknown", "", "", _lower_ascii(default_lang), {"raw": raw})


def normalize_bio_with_info(
    raw_bio: Union[Mapping[str, Any], Sequence[Any]],
    raw_info_structure: Optional[Mapping[str, Any]] = None,
    *,
    default_lang: str = "en",
) -> Dict[str, Any]:
    return {
        "bio": normalize_bio_semantics(raw_bio, default_lang=default_lang),
        "info_structure": normalize_info_structure(raw_info_structure or {}),
    }


# ---------------------------------------------------------------------------
# BRIDGE FUNCTIONS (Fixes AttributeError)
# ---------------------------------------------------------------------------

def normalize_bio_frame(payload: Mapping[str, Any], frame_type: str) -> BioFrame:
    """
    Construct a BioFrame from a raw dictionary payload.
    Used by aw_bridge for 'bio' and related types.
    """
    sem = normalize_bio_semantics(payload)
    
    # Construct the core Entity
    main_entity = Entity(
        name=sem.name,
        gender=sem.gender,
        lemmas=[sem.profession_lemma] if sem.profession_lemma else [],
        extra=sem.extra
    )

    return BioFrame(
        main_entity=main_entity,
        frame_type="bio",
        primary_profession_lemmas=[sem.profession_lemma] if sem.profession_lemma else [],
        nationality_lemmas=[sem.nationality_lemma] if sem.nationality_lemma else [],
        extra=sem.extra
    )


def normalize_entity_frame(payload: Mapping[str, Any], frame_type: str) -> Frame:
    """
    Construct a generic Entity frame (or fallback to BioFrame if it looks like a person).
    """
    if frame_type == "entity.person":
        return normalize_bio_frame(payload, "bio")

    name = _normalize_string(payload.get("name") or payload.get("label"))
    ent = Entity(
        name=name,
        entity_type=frame_type,
        extra=dict(payload)
    )
    return BioFrame(main_entity=ent, frame_type=frame_type, extra=dict(payload))


def normalize_event_frame(payload: Mapping[str, Any], frame_type: str) -> Event:
    """Construct a generic Event frame."""
    return Event(
        event_type=frame_type,
        participants={},
        extra=dict(payload)
    )


def normalize_relational_frame(payload: Mapping[str, Any], frame_type: str) -> Frame:
    """Construct a generic placeholder for relational frames."""
    return Event(event_type=frame_type, extra=dict(payload))


def normalize_narrative_frame(payload: Mapping[str, Any], frame_type: str) -> Frame:
    """Construct a generic placeholder for narrative frames."""
    return BioFrame(main_entity=Entity(name="Unknown"), frame_type=frame_type, extra=dict(payload))


def normalize_meta_frame(payload: Mapping[str, Any], frame_type: str) -> Frame:
    """Construct a generic placeholder for meta frames."""
    return BioFrame(main_entity=Entity(name="Meta"), frame_type=frame_type, extra=dict(payload))


def normalize_generic_frame(payload: Mapping[str, Any], frame_type: str) -> Frame:
    """Catch-all normalizer."""
    return BioFrame(main_entity=Entity(name="Generic"), frame_type=frame_type, extra=dict(payload))


__all__ = [
    "BioSemantics",
    "InfoStructure",
    "normalize_gender",
    "normalize_info_structure",
    "normalize_bio_semantics",
    "normalize_bio_with_info",
    # Bridge exports
    "normalize_bio_frame",
    "normalize_entity_frame",
    "normalize_event_frame",
    "normalize_relational_frame",
    "normalize_narrative_frame",
    "normalize_meta_frame",
    "normalize_generic_frame",
]