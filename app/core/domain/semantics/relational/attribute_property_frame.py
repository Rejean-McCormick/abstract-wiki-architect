# semantics\relational\attribute_property_frame.py
"""
semantics/relational/attribute_property_frame.py
------------------------------------------------

Relational / statement-level frame for simple attributes and properties.

This frame corresponds to the **Attribute / property** family described in
`docs/FRAMES_RELATIONAL.md` under the name `AttributeFrame`. It expresses
facts of the form:

    - "X is democratic."
    - "The river is navigable."
    - "The city is bilingual."
    - "X has property P = V."

The frame is intentionally small and language-neutral. It carries:

    - the subject entity,
    - a coarse attribute key,
    - a canonical value (usually lemma-like),
    - optional lexical hints for realization,
    - basic metadata (time, certainty, source, extra).

Surface realization (adjectives vs NPs, negation, modality, etc.) is handled
by the NLG pipeline and construction layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from semantics.types import Entity, TimeSpan


@dataclass
class AttributeFrame:
    """
    Simple attribute statement.

    Examples
    --------
        - "The party is democratic."
        - "The river is navigable."
        - "The city is bilingual."

    Semantics
    ---------
    subject:
        The thing being described (X).

    attribute:
        Coarse attribute category key, used as a domain-level feature
        identifier. Examples include:

            - "political_system"
            - "status"
            - "language_regime"
            - "navigability"

        The inventory is project-specific and loosely constrained.

    value:
        Canonical value for the attribute. In many cases this will be a
        lemma-like string such as "democratic", "bilingual", "navigable".
        For more complex attributes, it may be a small structured object
        or enum-like string.

    frame_type:
        Stable discriminator for routing. For attribute/property relations
        this is `"rel_attribute"`.

    id:
        Optional stable identifier for this statement (e.g. a knowledge-base
        statement ID). Useful for traceability and round-tripping but not
        required for generation.

    value_lemma:
        Optional lemma key for the value, if you want to decouple the
        semantic `value` from the lexeme that should realize it. When
        provided, the lexicon / constructions may prefer this over
        stringifying `value`.

    realization_hint:
        Optional hint for the construction layer about how to realize the
        value, e.g.:

            - "adjective"  → "X is democratic."
            - "np"         → "X is a democracy."
            - "pp"         → "X is in good condition."

        Engines are free to ignore this; it is advisory only.

    time:
        Optional `TimeSpan` indicating when the attribute applies (e.g. a
        particular year or period).

    certainty:
        Degree of confidence in the statement, from 0.0 (completely
        uncertain) to 1.0 (maximal confidence). Default is 1.0.

    source_id:
        Optional ID or handle pointing back to the original source statement
        (e.g. a Wikidata statement ID).

    extra:
        Open-ended map for additional metadata or source-specific fields
        that are not interpreted by the generic NLG pipeline.
    """

    # Core semantic roles
    subject: Entity  # X
    attribute: str  # coarse attribute key
    value: Any  # canonical value

    # Frame discriminator for routing / planning
    frame_type: str = "rel_attribute"

    # Optional metadata and lexical hints
    id: Optional[str] = None
    value_lemma: Optional[str] = None
    realization_hint: Optional[str] = None  # "adjective", "np", "pp", …

    # Context and provenance
    time: Optional[TimeSpan] = None
    certainty: float = 1.0
    source_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["AttributeFrame"]
