# app\core\domain\semantics\aw_bridge.py
# semantics\aw_bridge.py
# semantics/aw_bridge.py
"""
Bridging layer between external AbstractWiki-style JSON payloads and the
internal semantic frame dataclasses defined in :mod:`semantics.types`
and the family-specific modules.

This module is intentionally thin:

* It is responsible for:
  - basic validation of the external payload structure,
  - detecting the intended ``frame_type`` for each payload,
  - routing the payload to the appropriate normalization function.

* It is **not** responsible for:
  - detailed schema validation,
  - filling in defaults,
  - constructing dataclass instances directly.

Those tasks are delegated to :mod:`semantics.normalization`, which is the
single place that should know about quirks of upstream schemas.

The high-level API exposed here is:

    - ``frame_from_aw``: convert a single JSON payload into a Frame.
    - ``frames_from_aw``: convert a sequence of payloads into Frames.

The external JSON is assumed to be *AbstractWiki-like*:

    - It may contain a ``"frame_type"`` field with canonical strings like
      ``"bio"`` or ``"entity.organization"``.
    - If not, we try to infer a canonical frame type from secondary
      fields such as ``"type"``, ``"family"``, or ``"kind"``.

The internal canonical frame type strings are the ones documented in
the FRAMES_* docs (e.g. ``docs/FRAMES_ENTITY.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

from .types import Frame  # protocol / base type

# Normalization module is expected to provide the concrete converters.
from . import normalization


AWFramePayload = Mapping[str, Any]
AWMutablePayload = MutableMapping[str, Any]


__all__ = [
    "AWFramePayload",
    "UnknownFrameTypeError",
    "frame_from_aw",
    "frames_from_aw",
]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class UnknownFrameTypeError(KeyError):
    """Raised when we cannot detect or normalize the frame type of a payload."""

    def __init__(self, frame_type: str | None, payload: AWFramePayload):
        msg = f"Unknown or unsupported frame_type {frame_type!r}"
        super().__init__(msg)
        self.frame_type = frame_type
        self.payload = payload


# ---------------------------------------------------------------------------
# Frame type detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DetectedFrameType:
    """Small helper object for frame-type detection."""

    canonical: str
    source_field: str


_FRAME_TYPE_FALLBACK_KEYS: Sequence[str] = (
    "frame_type",  # preferred / canonical
    "type",
    "family",
    "kind",
)


def _coerce_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return str(value).strip() or None


def _normalize_raw_frame_type(raw: str) -> str:
    """
    Map loose / legacy identifiers to canonical frame_type strings.

    This function is the only place in this module that encodes
    knowledge about legacy naming conventions. All other normalization
    logic lives in :mod:`semantics.normalization`.
    """
    lower = raw.strip().lower()

    # Person / bio
    if lower in {"bio", "person", "person-bio", "person_bio"}:
        return "bio"

    # Entity families
    if lower in {"organization", "organisation", "org"}:
        return "entity.organization"
    if lower in {"gpe", "country", "state", "city", "municipality"}:
        return "entity.gpe"
    if lower in {"place", "geographic_feature", "geo"}:
        return "entity.place"
    if lower in {"facility", "infrastructure"}:
        return "entity.facility"
    if lower in {"astronomical_object", "astro_object", "celestial_body"}:
        return "entity.astronomical_object"
    if lower in {"taxon", "species"}:
        return "entity.taxon"
    if lower in {"chemical", "material"}:
        return "entity.chemical"
    if lower in {"artifact", "artefact"}:
        return "entity.artifact"
    if lower in {"vehicle", "craft"}:
        return "entity.vehicle"
    if lower in {"creative_work", "work"}:
        return "entity.creative_work"
    if lower in {"software", "website", "protocol", "standard"}:
        return "entity.software_or_standard"
    if lower in {"product", "brand"}:
        return "entity.product_or_brand"
    if lower in {"sports_team", "club", "team"}:
        return "entity.sports_team"
    if lower in {"competition", "tournament", "league"}:
        return "entity.competition"
    if lower in {"language", "lang"}:
        return "entity.language"
    if lower in {"religion", "belief_system", "ideology"}:
        return "entity.belief_system"
    if lower in {"discipline", "field", "theory"}:
        return "entity.discipline_or_theory"
    if lower in {"law", "treaty", "policy", "constitution"}:
        return "entity.legal_instrument"
    if lower in {"project", "program", "programme", "initiative"}:
        return "entity.project_or_program"
    if lower in {"fictional", "fictional_entity", "fiction"}:
        return "entity.fictional"

    # Event families (see docs/FRAMES_EVENT.md)
    if lower in {"event", "generic_event"}:
        return "event.generic"
    if lower in {"historical_event", "history_event"}:
        return "event.historical"
    if lower in {"conflict", "war", "battle"}:
        return "event.conflict"
    if lower in {"election", "referendum"}:
        return "event.election"
    if lower in {"disaster", "accident"}:
        return "event.disaster"
    if lower in {"scientific_milestone", "technical_milestone"}:
        return "event.scientific_milestone"
    if lower in {"cultural_event"}:
        return "event.cultural"
    if lower in {"sports_event", "match", "season"}:
        return "event.sports"
    if lower in {"legal_case", "court_case"}:
        return "event.legal_case"
    if lower in {"economic_event", "financial_event"}:
        return "event.economic"
    if lower in {"exploration", "expedition", "mission"}:
        return "event.exploration"
    if lower in {"life_event"}:
        return "event.life"

    # Relational families (FRAMES_RELATIONAL)
    if lower in {"definition", "classification"}:
        return "rel.definition"
    if lower in {"attribute", "property"}:
        return "rel.attribute"
    if lower in {"quantitative", "quantity"}:
        return "rel.quantitative"
    if lower in {"comparison", "ranking"}:
        return "rel.comparative"
    if lower in {"membership", "affiliation"}:
        return "rel.membership"
    if lower in {"role", "position", "office"}:
        return "rel.role"
    if lower in {"part_whole", "composition"}:
        return "rel.part_whole"
    if lower in {"ownership", "control"}:
        return "rel.ownership"
    if lower in {"spatial_relation", "spatial"}:
        return "rel.spatial"
    if lower in {"temporal_relation", "temporal"}:
        return "rel.temporal"
    if lower in {"causal", "influence"}:
        return "rel.causal"
    if lower in {"change_of_state", "change"}:
        return "rel.change_of_state"
    if lower in {"communication", "statement", "quote"}:
        return "rel.communication"
    if lower in {"opinion", "evaluation"}:
        return "rel.opinion"
    if lower in {"relation_bundle", "multi_fact"}:
        return "rel.bundle"

    # Narrative / aggregate families (FRAMES_NARRATIVE)
    if lower in {"timeline", "chronology"}:
        return "narr.timeline"
    if lower in {"career_summary", "season_summary", "campaign_summary"}:
        return "narr.career_or_season"
    if lower in {"development", "evolution"}:
        return "narr.development"
    if lower in {"reception", "impact"}:
        return "narr.reception"
    if lower in {"structure", "organization"}:
        return "narr.structure"
    if lower in {"comparison_set", "contrast"}:
        return "narr.comparison_set"
    if lower in {"list", "enumeration"}:
        return "narr.list"

    # Meta / article-level families (FRAMES_META)
    if lower in {"article", "document"}:
        return "meta.article"
    if lower in {"section", "section_summary"}:
        return "meta.section"
    if lower in {"source", "citation", "reference"}:
        return "meta.source"

    # If the string already looks canonical (contains a dot and a family prefix),
    # we just return it as-is.
    if "." in lower:
        return lower

    # Fallback: assume caller provided something we don't recognize;
    # let normalization handle (and potentially reject) it.
    return lower


def detect_frame_type(payload: AWFramePayload) -> DetectedFrameType:
    """
    Best-effort detection of canonical frame type from an AW payload.

    This is deliberately conservative: if we cannot find *any* suitable
    clue, we leave it to the caller to decide what to do.
    """
    for key in _FRAME_TYPE_FALLBACK_KEYS:
        raw = _coerce_to_str(payload.get(key))
        if raw:
            canonical = _normalize_raw_frame_type(raw)
            return DetectedFrameType(canonical=canonical, source_field=key)

    # No candidate found
    raise UnknownFrameTypeError(frame_type=None, payload=payload)


# ---------------------------------------------------------------------------
# Routing to normalization
# ---------------------------------------------------------------------------


def _normalize_by_family(
    detected: DetectedFrameType,
    payload: AWFramePayload,
) -> Frame:
    """
    Route a payload to the appropriate normalization function based on
    the canonical frame type prefix.

    The concrete functions live in :mod:`semantics.normalization`. Only
    their *signatures* are assumed here:

        - normalize_bio_frame(payload, frame_type) -> BioFrame
        - normalize_entity_frame(payload, frame_type) -> Frame
        - normalize_event_frame(payload, frame_type) -> Frame
        - normalize_relational_frame(payload, frame_type) -> Frame
        - normalize_narrative_frame(payload, frame_type) -> Frame
        - normalize_meta_frame(payload, frame_type) -> Frame

    Each function is responsible for dispatching within its own family
    (e.g. `entity.organization` vs `entity.gpe`).
    """
    ft = detected.canonical

    if ft.startswith("bio"):
        return normalization.normalize_bio_frame(payload, ft)

    if ft.startswith("entity."):
        return normalization.normalize_entity_frame(payload, ft)

    if ft.startswith("event."):
        return normalization.normalize_event_frame(payload, ft)

    if ft.startswith("rel.") or ft.startswith("relation."):
        return normalization.normalize_relational_frame(payload, ft)

    if ft.startswith("narr."):
        return normalization.normalize_narrative_frame(payload, ft)

    if ft.startswith("meta."):
        return normalization.normalize_meta_frame(payload, ft)

    # If the type didn’t match any known family prefix, allow the
    # normalization module to attempt a catch-all normalization. If it
    # doesn’t support it, we re-raise a clear error.
    if hasattr(normalization, "normalize_generic_frame"):
        return normalization.normalize_generic_frame(payload, ft)

    raise UnknownFrameTypeError(frame_type=ft, payload=payload)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def frame_from_aw(payload: AWFramePayload) -> Frame:
    """
    Convert a single AbstractWiki-style JSON payload into a semantic Frame.

    This function is pure and side-effect-free: it never mutates the
    incoming payload and never reaches out to external systems.

    :raises UnknownFrameTypeError:
        if the payload does not contain any usable frame-type information
        or if the canonical frame type cannot be handled.
    """
    detected = detect_frame_type(payload)
    return _normalize_by_family(detected, payload)


def frames_from_aw(payloads: Iterable[AWFramePayload]) -> list[Frame]:
    """
    Convert an iterable of AW payloads into a list of semantic Frames.

    This is a thin convenience wrapper over :func:`frame_from_aw`. It
    stops at the first error and propagates it to the caller. If you need
    “best-effort” behavior, you can wrap calls to :func:`frame_from_aw`
    in your own error-handling logic.
    """
    return [frame_from_aw(p) for p in payloads]