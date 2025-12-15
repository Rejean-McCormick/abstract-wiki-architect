# semantics\common\reference.py
"""
semantics/common/reference.py
=============================

Light-weight reference primitives shared by frame modules.

The semantic layer sometimes needs to *refer* to something without
embedding the full object:

- another entity / article (e.g. “see also …”),
- an event or frame elsewhere in the document,
- an external source / citation (URL, QID, DOI, …).

This module provides a small, implementation-oriented `Reference`
dataclass plus helpers to normalize “loose” inputs (strings, dicts) into
that canonical shape.

Design goals
------------

- Keep the representation generic and minimal.
- Avoid depending on higher-level frame types (`Entity`, `BioFrame`, …).
- Be convenient to construct from plain JSON / dicts.
- Be safe to ignore when a consumer is not interested in references
  (no required fields).

Typical usage
-------------

    from semantics.common.reference import (
        Reference,
        normalize_reference,
        entity_ref,
        source_ref,
    )

    # From structured data
    ref = Reference(
        kind="entity",
        target_id="Q7186",
        label="Marie Curie",
    )

    # From a loose dict (e.g. JSON)
    raw = {"id": "Q7186", "label": "Marie Curie"}
    ref = normalize_reference(raw, default_kind="entity")

    # From a simple string
    ref = normalize_reference("Marie Curie")   # kind="label"

    # Convenience constructors
    ref = entity_ref("Q7186", label="Marie Curie")
    src = source_ref(
        "doi:10.1000/xyz",
        label="Example Article",
        href="https://doi.org/10.1000/xyz",
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Reference:
    """
    Generic pointer to some external object (entity, frame, source, …).

    Fields
    ------

    kind:
        Free string describing what is being referenced, for example:

        - "entity"      – a person / organization / place / taxon, …
        - "frame"       – another semantic frame or event
        - "source"      – a bibliographic or web source
        - "section"     – a section or anchor in a document
        - "label"       – unlabeled / opaque reference (just text)

        The inventory is deliberately open; downstream code can normalize
        or restrict it as needed.

    target_id:
        Stable identifier for the target, if available:

        - Wikidata QID ("Q7186"),
        - DOI ("doi:10.1000/xyz"),
        - internal frame ID ("event:123"),
        - any other project-specific identifier.

        May be ``None`` when only a label or URL is known.

    label:
        Human-readable label (e.g. article title, person name, source
        title). This is optional and may be empty; callers should not
        assume it is present.

    href:
        Optional direct link (URL) to the referenced object. This can be
        a wiki page, external website, API endpoint, etc.

    extra:
        Arbitrary metadata for callers that need more structure (e.g.
        {"qid": "Q7186", "lang": "en"}). Consumers that do not care
        about it can ignore this field safely.

    Notes
    -----

    - All fields are optional except ``kind``; even then, callers are
      free to use a single generic value like "generic" if they do not
      wish to distinguish reference types.
    - The class is intentionally *not* tied to any particular citation
      or entity schema; higher-level frame modules can wrap or extend it
      if needed.
    """

    kind: str = "generic"
    target_id: Optional[str] = None
    label: str = ""
    href: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """
        Return True if the reference carries no useful information.

        This is helpful when a field is optional and may contain a
        partially filled `Reference` instance.
        """
        return not (self.target_id or self.label or self.href or self.extra)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the reference into a JSON-friendly dict.

        The result is stable and only contains JSON-serializable values
        (assuming ``extra`` does). Keys are always present; optional
        fields may be ``None`` or empty.
        """
        return {
            "kind": self.kind,
            "target_id": self.target_id,
            "label": self.label,
            "href": self.href,
            "extra": dict(self.extra) if self.extra is not None else {},
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], *, default_kind: str = "generic"
    ) -> "Reference":
        """
        Construct a `Reference` from a dict.

        Accepted keys (all optional):

        - "kind" / "type"
        - "target_id" / "id"
        - "label" / "title" / "name"
        - "href" / "url"
        - "extra"

        Any additional keys will be merged into ``extra`` if not already
        provided explicitly.

        Raises
        ------

        TypeError
            If `data` is not a dict.
        """
        if isinstance(data, cls):
            # Allow passing an already constructed Reference.
            return data

        if not isinstance(data, dict):
            raise TypeError(f"Reference.from_dict expects a dict, got {type(data)}")

        # Start with a shallow copy so we can pop keys.
        raw = dict(data)

        kind = str(raw.pop("kind", raw.pop("type", default_kind)) or default_kind)

        target_id = raw.pop("target_id", raw.pop("id", None))

        # Prefer an explicit "label", then common alternatives.
        label_value = raw.pop("label", raw.pop("title", raw.pop("name", "")))
        label = "" if label_value is None else str(label_value)

        href = raw.pop("href", raw.pop("url", None))

        extra_raw = raw.pop("extra", None)
        extra: Dict[str, Any] = {}
        if isinstance(extra_raw, dict):
            extra.update(extra_raw)

        # Any remaining keys are folded into extra as well.
        for k, v in raw.items():
            # Do not overwrite existing keys coming from explicit "extra".
            if k not in extra:
                extra[k] = v

        return cls(
            kind=kind,
            target_id=target_id,
            label=label,
            href=href,
            extra=extra,
        )


# ----------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------


def normalize_reference(
    obj: Any, *, default_kind: str = "generic"
) -> Optional[Reference]:
    """
    Normalize an arbitrary value into a `Reference` instance.

    This is intended for callers that accept flexible JSON-like input
    but want a predictable internal type.

    Accepted inputs
    ---------------

    - ``None``:
        Returns ``None`` (no reference).
    - ``Reference``:
        Returned as-is, except that a missing/empty ``kind`` is replaced
        with ``default_kind``.
    - ``str``:
        Treated as a pure label, with ``kind="label"``.
    - ``dict``:
        Parsed via :meth:`Reference.from_dict`, with ``default_kind``.

    Any other type results in ``TypeError``.
    """
    if obj is None:
        return None

    if isinstance(obj, Reference):
        if not obj.kind:
            obj.kind = default_kind
        return obj

    if isinstance(obj, str):
        return Reference(kind="label", label=obj)

    if isinstance(obj, dict):
        return Reference.from_dict(obj, default_kind=default_kind)

    raise TypeError(
        f"Cannot normalize object of type {type(obj)} to Reference; "
        f"expected None, str, dict, or Reference."
    )


# ----------------------------------------------------------------------
# Convenience constructors for common kinds
# ----------------------------------------------------------------------


def entity_ref(
    target_id: Optional[str] = None,
    *,
    label: str = "",
    href: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Reference:
    """
    Convenience constructor for an entity reference.

    Example:

        marie = entity_ref("Q7186", label="Marie Curie")
    """
    return Reference(
        kind="entity",
        target_id=target_id,
        label=label,
        href=href,
        extra=dict(extra or {}),
    )


def frame_ref(
    target_id: Optional[str] = None,
    *,
    label: str = "",
    href: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Reference:
    """
    Convenience constructor for a reference to another semantic frame.

    This is intentionally agnostic about the concrete frame type; the
    caller is free to encode that in ``target_id`` or ``extra``.
    """
    return Reference(
        kind="frame",
        target_id=target_id,
        label=label,
        href=href,
        extra=dict(extra or {}),
    )


def source_ref(
    target_id: Optional[str] = None,
    *,
    label: str = "",
    href: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Reference:
    """
    Convenience constructor for a reference to a source / citation.

    Examples:

        # DOI-only reference
        src = source_ref("doi:10.1000/xyz", label="Example Article")

        # URL-only reference
        src = source_ref(
            None,
            label="Project homepage",
            href="https://example.org",
        )
    """
    return Reference(
        kind="source",
        target_id=target_id,
        label=label,
        href=href,
        extra=dict(extra or {}),
    )


__all__ = [
    "Reference",
    "normalize_reference",
    "entity_ref",
    "frame_ref",
    "source_ref",
]
