# semantics\narrative\list_enumeration_frame.py
"""
semantics/narrative/list_enumeration_frame.py
---------------------------------------------

Narrative / aggregate frame for list-style enumerations.

This module defines a light-weight, language-independent representation
for facts whose content is naturally expressed as a list, for example:

    - "X produces A, B, and C."
    - "The main types of Y are A, B, and C."
    - "Notable players include A, B, and C."

The frame corresponds to the "List / enumeration frame" in the global
frame inventory (family 55, canonical frame_type: "aggregate.list").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity
from semantics.all_frames import register_frame_type


@dataclass
class ListItem:
    """
    Single item in a list enumeration.

    Each item can be represented either as an `Entity` (for cases where
    the list is over entities like people, teams, works, etc.) or as a
    free-form label when an entity object is not available or not
    needed.

    Fields
    ------

    entity:
        Optional `Entity` if the item corresponds to a concrete entity
        in the knowledge base (person, organization, work, etc.). For
        example, a player, a product, or a city.

    label:
        Optional label for the item when you either do not have, or do
        not want to use, a full `Entity`. This might be a lemma-style
        label such as "football", "basketball", "volleyball" for
        listing sports, or a short name for an abstract concept.

    properties:
        Optional map of additional attributes about the item, using
        JSON-friendly values. Example keys:

            {
                "role": "captain",
                "position": "forward",
                "year": 2023,
                "is_notable": True
            }

        The exact schema is intentionally unconstrained and can be
        tailored by upstream pipelines.

    salience:
        Optional integer hint indicating the relative importance or
        prominence of the item within the list. Higher values can be
        interpreted as "more salient". Planners may use this to decide
        which items to include when the list is too long to fully
        realize.
    """

    entity: Optional[Entity] = None
    label: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    salience: Optional[int] = None


@register_frame_type("aggregate.list")
@dataclass
class ListEnumerationFrame:
    """
    List / enumeration aggregate frame.

    This frame captures the semantics of a list of items associated with
    an (optional) subject, along with hints about how the list should be
    interpreted and realized.

    Typical examples
    ----------------

    - "X produces A, B, and C."       → subject_id = "X", list_kind = "products"
    - "The main types of Y are A…"    → subject_id = "Y", list_kind = "types"
    - "Notable players include A…"    → subject_id = "Team", list_kind = "notable_players"

    Fields
    ------

    frame_type:
        Canonical frame type string for this family. For list /
        enumeration frames this is "aggregate.list". It is used by the
        generic frame registry (`semantics.all_frames`) and by routing /
        planning code.

    subject_id:
        Optional identifier for the subject that this list is "about".
        In many NLG contexts this will be the ID of the article subject
        (e.g. a Wikidata QID or internal page ID). Keeping only an ID
        here avoids forcing a dependency on a particular entity frame
        type.

        For purely stand-alone lists (no explicit subject in the
        wording), this may be left as None.

    list_kind:
        Short label describing what the items represent, for example:

            "members"
            "features"
            "subtypes"
            "products"
            "notable_players"
            "languages"

        This helps planners choose more precise constructions ("X
        features A, B, and C", "X's main products are…", etc.).

    ordering:
        Optional hint about the intended ordering of the items. Typical
        values include:

            "none"
            "importance"
            "alphabetical"
            "chronological"
            "by_role"

        The label is free-form; planners may use or ignore it.

    scope:
        Optional domain qualifier describing the scope in which the
        enumeration holds, for example:

            "worldwide"
            "domestic"
            "regular_season"
            "current"

        This is a simple string; any further structuring is left to
        upstream semantics.

    items:
        List of :class:`ListItem` objects representing the actual
        members of the list. Each item may be backed by an `Entity` or
        just a label.

    preferred_realization:
        Optional hint to the NLG layer about how to realize the list in
        context. Typical values could be:

            "single-sentence"
            "multi-sentence"
            "bulleted"

        These are only preferences; realizers may ignore them if the
        surrounding context dictates a different style.

    extra:
        Free-form metadata bag for pipeline-specific information,
        provenance, or precomputed helpers. It is not interpreted by the
        generic semantics layer.
    """

    #: Stable frame type string used by the registry and generic Frame protocol.
    frame_type: ClassVar[str] = "aggregate.list"

    subject_id: Optional[str] = None
    list_kind: Optional[str] = None
    ordering: Optional[str] = None
    scope: Optional[str] = None

    items: List[ListItem] = field(default_factory=list)

    preferred_realization: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ListEnumerationFrame", "ListItem"]
