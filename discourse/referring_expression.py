# discourse/referring_expression.py
"""
discourse/referring_expression.py
=================================

Language-agnostic referring-expression choice.

This module decides *how* to refer to an entity in discourse context
(pronoun, full name, short name, descriptive NP), but it does **not**
perform language-specific morphology.

Architectural role
------------------
This helper lives below planning and alongside lexical resolution:

    normalized semantics
      -> planning / construction packaging
      -> lexical resolution / NP choice
      -> morphology / realization

The output is a small, renderer-neutral NP specification that a later
morphology / realization layer can turn into a surface string.

Design goals
------------
- Accept both dict-like entities and semantic dataclass objects.
- Remain tolerant of legacy payloads.
- Be deterministic and side-effect free.
- Keep heuristics explicit and inspectable in debug metadata.
- Avoid doing morphology or language-specific inflection.

Expected entity inputs
----------------------
Typical fields used when present:

    {
        "id": "Q123",
        "name": "Marie Curie",
        "short_name": "Curie",
        "gender": "female",
        "number": "sg",
        "human": True,
        "person": 3,
        "type": "person",
        "entity_type": "person",
        "head_lemma": "physicist",
        "lemmas": ["physicist", "chemist"],
        "features": {...},
        "extra": {...},
    }

Expected discourse_info inputs
------------------------------
Typical fields used when present:

    {
        "is_first_mention": bool,
        "is_topic": bool,
        "is_focus": bool,

        # Optional hard overrides:
        "force_pronoun": bool,
        "force_name": bool,
        "force_short_name": bool,
        "force_description": bool,

        # Optional safety / ambiguity hints:
        "avoid_pronoun": bool,
        "pronoun_ambiguous": bool,
        "competing_referents": int,
        "recent_same_gender_human_mentions": int,
    }

Expected lang_profile inputs
----------------------------
Optional config section:

    {
        "referring_expression": {
            "allow_pronouns": true,
            "pronouns_for_humans_only": true,
            "allow_pronouns_on_first_mention": false,
            "use_pronoun_for_topic_after_first_mention": true,
            "use_pronoun_for_focus_after_first_mention": true,
            "use_short_name_after_first_mention": true,
            "prefer_name_over_description": true,
            "allow_short_name_when_topic": true
        }
    }

Output NP specification
-----------------------
select_np_spec(...) returns a dict like:

    {
        "realization_type": "pronoun" | "name" | "short_name" | "description",
        "lemma": "Marie Curie" | "physicist" | None,
        "features": {
            "definiteness": "def",
            "person": 3,
            "number": "sg",
            "gender": "fem",
            "human": True,
            "pronoun_type": "personal"
        },
        "referent_id": "Q123" | None,
        "metadata": {
            "decision": "pronoun",
            "reason": "topic_after_first_mention",
            "entity_type": "person"
        }
    }
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict, Optional


REALIZATION_PRONOUN = "pronoun"
REALIZATION_NAME = "name"
REALIZATION_SHORT_NAME = "short_name"
REALIZATION_DESCRIPTION = "description"

DEFAULT_DISCOURSE_INFO: Dict[str, Any] = {
    "is_first_mention": True,
    "is_topic": False,
    "is_focus": False,
    "force_pronoun": False,
    "force_name": False,
    "force_short_name": False,
    "force_description": False,
    "avoid_pronoun": False,
    "pronoun_ambiguous": False,
    "competing_referents": 0,
    "recent_same_gender_human_mentions": 0,
}


# ---------------------------------------------------------------------------
# Generic access helpers
# ---------------------------------------------------------------------------


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _entity_field(entity: Any, key: str, default: Any = None) -> Any:
    """
    Read a field from either:
    - a mapping-like entity
    - a dataclass / object with attributes
    - nested .features / .extra mappings
    """
    if entity is None:
        return default

    if _is_mapping(entity):
        mapping = entity
        if key in mapping:
            return mapping.get(key, default)

        features = mapping.get("features")
        if _is_mapping(features) and key in features:
            return features.get(key, default)

        extra = mapping.get("extra")
        if _is_mapping(extra) and key in extra:
            return extra.get(key, default)

        return default

    if hasattr(entity, key):
        return getattr(entity, key)

    features = getattr(entity, "features", None)
    if _is_mapping(features) and key in features:
        return features.get(key, default)

    extra = getattr(entity, "extra", None)
    if _is_mapping(extra) and key in extra:
        return extra.get(key, default)

    return default


def _normalize_discourse_info(discourse_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if discourse_info is None:
        return dict(DEFAULT_DISCOURSE_INFO)

    info = dict(DEFAULT_DISCOURSE_INFO)
    info.update(discourse_info)
    return info


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    return bool(value)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        text = _safe_str(value)
        if text:
            return text
    return None


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _get_ref_cfg(lang_profile: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(lang_profile, dict):
        return {}
    cfg = lang_profile.get("referring_expression", {})
    return cfg if isinstance(cfg, dict) else {}


def _flag(cfg: Dict[str, Any], key: str, default: bool) -> bool:
    value = cfg.get(key)
    if value is None:
        return default
    return bool(value)


# ---------------------------------------------------------------------------
# Entity normalization helpers
# ---------------------------------------------------------------------------


def _entity_id(entity: Any) -> Optional[str]:
    return _first_nonempty(
        _entity_field(entity, "id"),
        _entity_field(entity, "entity_id"),
        _entity_field(entity, "qid"),
    )


def _entity_name(entity: Any) -> Optional[str]:
    return _first_nonempty(
        _entity_field(entity, "name"),
        _entity_field(entity, "label"),
        _entity_field(entity, "display_name"),
    )


def _entity_short_name(entity: Any) -> Optional[str]:
    return _first_nonempty(
        _entity_field(entity, "short_name"),
        _entity_field(entity, "surname"),
        _entity_field(entity, "family_name"),
    )


def _entity_gender(entity: Any) -> Optional[str]:
    """
    Normalize gender labels to a small canonical set.

    Returns:
        "fem" | "masc" | "other" | None
    """
    g_raw = _entity_field(entity, "gender")
    if not g_raw:
        return None

    g = str(g_raw).strip().lower()

    fem_values = {
        "f",
        "fem",
        "female",
        "woman",
        "girl",
    }
    masc_values = {
        "m",
        "masc",
        "male",
        "man",
        "boy",
    }
    other_values = {
        "other",
        "nonbinary",
        "non-binary",
        "nb",
        "neutral",
        "unknown",
        "unspecified",
    }

    if g in fem_values or g.startswith("fem"):
        return "fem"
    if g in masc_values or g.startswith("masc"):
        return "masc"
    if g in other_values:
        return "other"
    return "other"


def _entity_number(entity: Any) -> str:
    n_raw = _entity_field(entity, "number", "sg")
    n = str(n_raw).strip().lower()
    if n in {"pl", "plural", "p"}:
        return "pl"
    return "sg"


def _entity_person(entity: Any) -> int:
    p_raw = _entity_field(entity, "person", 3)
    try:
        person = int(p_raw)
    except Exception:
        return 3
    if person not in (1, 2, 3):
        return 3
    return person


def _entity_type(entity: Any) -> Optional[str]:
    return _first_nonempty(
        _entity_field(entity, "entity_type"),
        _entity_field(entity, "type"),
        _entity_field(entity, "kind"),
    )


def _entity_is_human(entity: Any) -> bool:
    explicit = _entity_field(entity, "human")
    if explicit is not None:
        return bool(explicit)

    entity_type = (_entity_type(entity) or "").lower()
    return entity_type in {
        "person",
        "human",
        "person_entity",
        "fictional_person",
        "fictional_character",
        "character",
    }


def _entity_lemmas(entity: Any) -> list[str]:
    lemmas = _entity_field(entity, "lemmas")
    if isinstance(lemmas, list):
        return [str(x).strip() for x in lemmas if str(x).strip()]
    if isinstance(lemmas, tuple):
        return [str(x).strip() for x in lemmas if str(x).strip()]
    return []


def _description_head(entity: Any) -> str:
    """
    Choose a neutral lemma/head for a descriptive NP fallback.
    """
    head = _first_nonempty(
        _entity_field(entity, "head_lemma"),
        _entity_field(entity, "description_lemma"),
        _entity_field(entity, "role"),
        _entity_field(entity, "class_lemma"),
    )
    if head:
        return head

    lemmas = _entity_lemmas(entity)
    if lemmas:
        return lemmas[0]

    entity_type = (_entity_type(entity) or "").strip().lower()
    type_fallbacks = {
        "person": "person",
        "human": "person",
        "organization": "organization",
        "company": "company",
        "institution": "institution",
        "place": "place",
        "city": "city",
        "country": "country",
        "region": "region",
        "fictional_character": "character",
        "character": "character",
        "event": "event",
        "work": "work",
    }
    if entity_type in type_fallbacks:
        return type_fallbacks[entity_type]

    label = _first_nonempty(_entity_field(entity, "label"))
    if label:
        return label

    return "entity"


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _build_base_features(entity: Any) -> Dict[str, Any]:
    """
    Base realization-neutral features for any NP referring to this entity.
    """
    feats: Dict[str, Any] = {
        "person": _entity_person(entity),
        "number": _entity_number(entity),
        "gender": _entity_gender(entity),
        "human": _entity_is_human(entity),
        "definiteness": "def",
    }

    entity_type = _entity_type(entity)
    if entity_type:
        feats["entity_type"] = entity_type

    return feats


# ---------------------------------------------------------------------------
# Core decision logic
# ---------------------------------------------------------------------------


def should_use_pronoun(
    entity: Any,
    discourse_info: Dict[str, Any],
    lang_profile: Dict[str, Any],
) -> bool:
    """
    Decide whether to use a pronoun in this context.

    High-level rules:
    - Explicit caller override wins unless pronouns are globally disabled.
    - By default, avoid pronouns on first mention.
    - Avoid pronouns when discourse explicitly marks ambiguity risk.
    - Respect human-only pronoun policy if enabled.
    - Prefer pronouns for topic/focus after first mention.
    """
    info = _normalize_discourse_info(discourse_info)
    cfg = _get_ref_cfg(lang_profile)

    allow_pronouns = _flag(cfg, "allow_pronouns", True)
    if not allow_pronouns:
        return False

    if _safe_bool(info.get("avoid_pronoun"), False):
        return False

    if _safe_bool(info.get("pronoun_ambiguous"), False):
        return False

    competing = _safe_int(info.get("competing_referents"), 0)
    if competing > 0:
        return False

    same_gender_mentions = _safe_int(info.get("recent_same_gender_human_mentions"), 0)
    if same_gender_mentions > 0:
        return False

    if _safe_bool(info.get("force_pronoun"), False):
        if _flag(cfg, "pronouns_for_humans_only", True) and not _entity_is_human(entity):
            return False
        return True

    is_first_mention = _safe_bool(info.get("is_first_mention"), True)
    if is_first_mention and not _flag(cfg, "allow_pronouns_on_first_mention", False):
        return False

    human_only_pronouns = _flag(cfg, "pronouns_for_humans_only", True)
    if human_only_pronouns and not _entity_is_human(entity):
        return False

    if _safe_bool(info.get("is_topic"), False) and _flag(
        cfg,
        "use_pronoun_for_topic_after_first_mention",
        True,
    ):
        return True

    if _safe_bool(info.get("is_focus"), False) and _flag(
        cfg,
        "use_pronoun_for_focus_after_first_mention",
        True,
    ):
        return True

    return _flag(cfg, "allow_unmarked_pronouns_after_first_mention", True)


def should_use_short_name(
    entity: Any,
    discourse_info: Dict[str, Any],
    lang_profile: Dict[str, Any],
) -> bool:
    """
    Decide whether to use a short name (surname, family name, nickname, etc.).
    """
    info = _normalize_discourse_info(discourse_info)
    cfg = _get_ref_cfg(lang_profile)

    if _safe_bool(info.get("is_first_mention"), True):
        return False

    short_name = _entity_short_name(entity)
    if not short_name:
        return False

    full_name = _entity_name(entity)
    if full_name and short_name.strip() == full_name.strip():
        return False

    if not _flag(cfg, "use_short_name_after_first_mention", True):
        return False

    if _safe_bool(info.get("is_topic"), False):
        return _flag(cfg, "allow_short_name_when_topic", True)

    return True


# ---------------------------------------------------------------------------
# NP spec builders
# ---------------------------------------------------------------------------


def _build_metadata(entity: Any, decision: str, reason: str) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "decision": decision,
        "reason": reason,
        "entity_type": _entity_type(entity),
    }
    short_name = _entity_short_name(entity)
    if short_name:
        meta["short_name_available"] = True
    return meta


def _build_pronoun_spec(entity: Any, reason: str) -> Dict[str, Any]:
    feats = _build_base_features(entity)
    feats["pronoun_type"] = "personal"
    return {
        "realization_type": REALIZATION_PRONOUN,
        "lemma": None,
        "features": feats,
        "referent_id": _entity_id(entity),
        "metadata": _build_metadata(entity, REALIZATION_PRONOUN, reason),
    }


def _build_full_name_spec(entity: Any, reason: str) -> Dict[str, Any]:
    name = _entity_name(entity)
    if not name:
        return _build_description_spec(entity, reason="missing_name_fallback")

    feats = _build_base_features(entity)
    feats["named_entity"] = True
    return {
        "realization_type": REALIZATION_NAME,
        "lemma": name,
        "features": feats,
        "referent_id": _entity_id(entity),
        "metadata": _build_metadata(entity, REALIZATION_NAME, reason),
    }


def _build_short_name_spec(entity: Any, reason: str) -> Dict[str, Any]:
    short = _entity_short_name(entity)
    if not short:
        return _build_full_name_spec(entity, reason="missing_short_name_fallback")

    feats = _build_base_features(entity)
    feats["named_entity"] = True
    feats["short_form"] = True
    return {
        "realization_type": REALIZATION_SHORT_NAME,
        "lemma": short,
        "features": feats,
        "referent_id": _entity_id(entity),
        "metadata": _build_metadata(entity, REALIZATION_SHORT_NAME, reason),
    }


def _build_description_spec(entity: Any, reason: str) -> Dict[str, Any]:
    head = _description_head(entity)
    feats = _build_base_features(entity)
    feats["definiteness"] = "def"
    return {
        "realization_type": REALIZATION_DESCRIPTION,
        "lemma": head,
        "features": feats,
        "referent_id": _entity_id(entity),
        "metadata": _build_metadata(entity, REALIZATION_DESCRIPTION, reason),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_np_spec(
    entity: Any,
    discourse_info: Optional[Dict[str, Any]],
    lang_profile: Dict[str, Any],
    *,
    allow_description_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Decide how to refer to `entity` in the current discourse context.

    Precedence:
    1. explicit force_description
    2. explicit force_name
    3. explicit / heuristic pronoun
    4. explicit / heuristic short name
    5. full name
    6. descriptive fallback
    7. opaque last-resort description ("entity")

    Returns:
        dict with keys:
            - realization_type
            - lemma
            - features
            - referent_id
            - metadata
    """
    info = _normalize_discourse_info(discourse_info)

    if _safe_bool(info.get("force_description"), False):
        return _build_description_spec(entity, reason="forced_description")

    if _safe_bool(info.get("force_name"), False):
        return _build_full_name_spec(entity, reason="forced_name")

    if should_use_pronoun(entity, info, lang_profile):
        reason = "forced_pronoun" if _safe_bool(info.get("force_pronoun"), False) else (
            "topic_after_first_mention"
            if _safe_bool(info.get("is_topic"), False)
            else "focus_after_first_mention"
            if _safe_bool(info.get("is_focus"), False)
            else "repeated_mention_pronoun"
        )
        return _build_pronoun_spec(entity, reason=reason)

    if _safe_bool(info.get("force_short_name"), False):
        return _build_short_name_spec(entity, reason="forced_short_name")

    if should_use_short_name(entity, info, lang_profile):
        return _build_short_name_spec(entity, reason="short_name_after_first_mention")

    if _entity_name(entity):
        return _build_full_name_spec(entity, reason="default_named_entity")

    if allow_description_fallback:
        return _build_description_spec(entity, reason="description_fallback")

    return {
        "realization_type": REALIZATION_DESCRIPTION,
        "lemma": "entity",
        "features": _build_base_features(entity),
        "referent_id": _entity_id(entity),
        "metadata": _build_metadata(entity, REALIZATION_DESCRIPTION, "opaque_last_resort"),
    }


__all__ = [
    "select_np_spec",
    "should_use_pronoun",
    "should_use_short_name",
]