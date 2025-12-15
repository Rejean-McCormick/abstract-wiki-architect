# semantics\common\location.py
"""
semantics/common/location.py
============================

Small helper utilities for working with :class:`Location` objects.

The core semantic dataclasses live in :mod:`semantics.types`. This module
adds a few pragmatic helpers that higher-level code (AW bridges, CSV
readers, etc.) can use to:

- Accept "messy" inputs (strings, dicts, Entities),
- Normalize them into :class:`Location` instances,
- Convert back into :class:`Entity` when needed.

Design goals
------------

- Keep the API tiny and predictable.
- Accept loose inputs but never mutate caller-owned objects.
- Avoid importing heavy modules; just rely on :mod:`semantics.types`.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from semantics.types import Entity, Location


# ---------------------------------------------------------------------------
# Core normalization helpers
# ---------------------------------------------------------------------------


def as_location(
    value: Any,
    *,
    default_kind: Optional[str] = None,
) -> Optional[Location]:
    """
    Coerce an arbitrary value into a :class:`Location`, if possible.

    This is the main entry point for callers that receive loosely-typed
    data (e.g. from JSON or Z-Objects).

    Accepted inputs
    ---------------

    - ``None`` → returns ``None``.
    - :class:`Location` → returned as-is (optionally patched with
      ``default_kind`` if ``kind`` is empty).
    - :class:`Entity` → converted via :func:`location_from_entity`.
    - ``str`` → simple label like ``"Paris"``.
    - ``Mapping`` → dict-like; interpreted by :func:`_location_from_mapping`.

    Any other type results in ``None`` (caller can decide how to handle that).

    Parameters
    ----------
    value:
        The object to interpret as a location.
    default_kind:
        Optional fallback kind (e.g. ``"city"``) if the resulting
        location has no ``kind`` set.

    Returns
    -------
    Location | None
        A new :class:`Location` instance, or ``None`` if the value could
        not be interpreted as a location.
    """
    if value is None:
        return None

    # Already a Location
    if isinstance(value, Location):
        if default_kind and not value.kind:
            return replace(value, kind=default_kind)
        return value

    # Entity → Location
    if isinstance(value, Entity):
        loc = location_from_entity(value, fallback_kind=default_kind)
        return loc

    # Simple string label
    if isinstance(value, str):
        return Location(name=value.strip(), kind=default_kind or None)

    # Dict-like
    if isinstance(value, Mapping):
        loc = _location_from_mapping(value)
        if loc and default_kind and not loc.kind:
            loc.kind = default_kind  # type: ignore[assignment]
        return loc

    # Unknown / unsupported type
    return None


def location_from_entity(
    entity: Entity,
    *,
    fallback_kind: Optional[str] = None,
) -> Location:
    """
    Create a :class:`Location` from an :class:`Entity`.

    This is useful when callers use :class:`Entity` for everything but
    want to make it explicit that a particular entity is used as a
    location (e.g. event ``location`` field).

    Heuristics
    ----------

    - ``id`` is copied verbatim.
    - ``name`` is copied verbatim.
    - ``kind`` is taken from ``entity.entity_type`` if it looks like a
      place-type (``"place"``, ``"city"``, ``"country"``, ``"region"`` …),
      otherwise from ``fallback_kind``.
    - ``country_code`` is derived from common metadata keys in
      ``entity.extra`` (``"country_code"``, ``"iso_country_code"``,
      ``"iso_3166_1_alpha2"``).
    - ``features`` / ``extra`` are shallow copies of the entity’s fields,
      so the caller can mutate the :class:`Location` without affecting
      the original :class:`Entity`.

    Parameters
    ----------
    entity:
        Source entity to reinterpret as a location.
    fallback_kind:
        Kind to use if the entity does not advertise a place-like type.

    Returns
    -------
    Location
        A new :class:`Location` instance.
    """
    place_like_types = {
        "place",
        "city",
        "town",
        "village",
        "country",
        "region",
        "province",
        "state",
        "island",
        "district",
    }

    kind: Optional[str] = None
    if entity.entity_type and entity.entity_type.lower() in place_like_types:
        kind = entity.entity_type
    elif fallback_kind:
        kind = fallback_kind

    extra_meta = dict(entity.extra or {})
    country_code = _extract_country_code(extra_meta)

    return Location(
        id=entity.id,
        name=entity.name,
        kind=kind,
        country_code=country_code,
        features=dict(entity.features or {}),
        extra=extra_meta,
    )


def location_to_entity(
    location: Location,
    *,
    entity_type: str = "place",
) -> Entity:
    """
    Convert a :class:`Location` back into a generic :class:`Entity`.

    This can be convenient when constructions or discourse modules
    expect entities but the upstream data model uses :class:`Location`
    for certain slots.

    Parameters
    ----------
    location:
        The location to convert.
    entity_type:
        ``Entity.entity_type`` to use for the resulting entity.
        Defaults to ``"place"``.

    Returns
    -------
    Entity
        A new :class:`Entity` instance.
    """
    return Entity(
        id=location.id,
        name=location.name,
        gender="unknown",
        human=False,
        entity_type=entity_type,
        lemmas=[],
        features=dict(location.features or {}),
        extra=dict(location.extra or {}),
    )


def is_empty_location(location: Location) -> bool:
    """
    Return ``True`` if ``location`` carries no meaningful information.

    This is mostly a convenience for callers that want to avoid emitting
    locative phrases like “in ” when the location is effectively empty.

    Criteria
    --------

    A location is considered *empty* if:

    - ``name`` is empty/whitespace, and
    - ``id``, ``kind``, ``country_code`` are all ``None``, and
    - ``features`` and ``extra`` are empty dicts.
    """
    if location.name.strip():
        return False

    if location.id is not None:
        return False
    if location.kind is not None:
        return False
    if location.country_code is not None:
        return False
    if location.features:
        return False
    if location.extra:
        return False

    return True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _location_from_mapping(data: Mapping[str, Any]) -> Optional[Location]:
    """
    Interpret a dict-like object as a :class:`Location`.

    Supported keys (all optional)
    -----------------------------

    - ``"id"``:       explicit identifier (string)
    - ``"wikidata_qid"`` / ``"qid"``: used as ``id`` if ``"id"`` is absent
    - ``"name"`` / ``"label"`` / ``"title"``: human-readable name
    - ``"kind"`` / ``"location_type"`` / ``"type"``: coarse location kind
    - ``"country_code"`` / ``"countryCode"`` / ``"iso_country_code"`` /
      ``"iso_3166_1_alpha2"``: ISO-style country code
    - ``"features"``:  dict of features (copied as-is)
    - ``"extra"``:     dict of extra metadata (copied as-is)

    Any other keys are left untouched and stored in ``extra`` so that
    no information is silently lost.

    Returns
    -------
    Location | None
        A :class:`Location` if at least a name or id can be recovered,
        otherwise ``None``.
    """
    # Basic scalar fields
    raw_id = _extract_id(data)
    name = _extract_name(data)
    kind = _extract_kind(data)
    country_code = _extract_country_code(data)

    # If *nothing* identifiable is present, bail out
    if not (raw_id or (name and name.strip())):
        return None

    # Features / extra
    features = dict(data.get("features") or {})
    extra = dict(data.get("extra") or {})

    # Preserve all unknown keys in extra to avoid dropping information
    for key, value in data.items():
        if key in {
            "id",
            "wikidata_qid",
            "qid",
            "name",
            "label",
            "title",
            "kind",
            "location_type",
            "type",
            "country",
            "country_code",
            "countryCode",
            "iso_country_code",
            "iso_3166_1_alpha2",
            "features",
            "extra",
        }:
            continue
        if key not in extra:
            extra[key] = value

    return Location(
        id=raw_id,
        name=name or "",
        kind=kind,
        country_code=country_code,
        features=features,
        extra=extra,
    )


def _extract_id(data: Mapping[str, Any]) -> Optional[str]:
    """
    Heuristic extraction of an identifier from a mapping.
    """
    id_val = data.get("id")
    if isinstance(id_val, str) and id_val.strip():
        return id_val.strip()

    # Common Wikidata-style keys
    for key in ("wikidata_qid", "qid"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


def _extract_name(data: Mapping[str, Any]) -> Optional[str]:
    """
    Heuristic extraction of a human-readable name / label.
    """
    for key in ("name", "label", "title"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_kind(data: Mapping[str, Any]) -> Optional[str]:
    """
    Heuristic extraction of a coarse location kind.
    """
    for key in ("kind", "location_type", "type"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_country_code(data: Mapping[str, Any]) -> Optional[str]:
    """
    Heuristic extraction of a country code from a mapping.

    Prefers explicit ISO-style fields, but will also interpret
    a two-letter uppercase ``"country"`` value as a code.
    """
    for key in (
        "country_code",
        "countryCode",
        "iso_country_code",
        "iso_3166_1_alpha2",
    ):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()

    # Fallback: guess from "country" if it looks like a code
    country = data.get("country")
    if isinstance(country, str):
        c = country.strip()
        if len(c) == 2 and c.isalpha():
            return c.upper()

    return None


__all__ = [
    "as_location",
    "location_from_entity",
    "location_to_entity",
    "is_empty_location",
]
