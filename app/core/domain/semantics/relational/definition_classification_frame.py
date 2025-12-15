# semantics\relational\definition_classification_frame.py
"""
semantics/relational/definition_classification_frame.py
-------------------------------------------------------

Relational frame for simple definitional / classification statements of
the form:

    - "X is a Y."
    - "X is a Y Z."
    - "X is a type of Y."

This is the workhorse frame for encyclopedic first sentences and other
short definitional clauses. It captures:

    - what is being defined (the *subject*),
    - which supertype(s) it is classified under,
    - which modifiers refine that classification (e.g. nationality,
      profession subtype, status, fictional vs. real, etc.),
    - whether the relation is "instance-of" or "subclass-of".

The frame is language-neutral. Surface realizations (choice of copula,
article, word order, agreement, etc.) are handled by downstream
constructions and morphology.

Typical examples
================

    - "Douglas Adams was a British writer."
        subject            → Douglas Adams
        definitional_relation → "instance-of"
        supertype_lemmas   → ["writer"]
        modifier_lemmas    → ["british"]

    - "Python is a high-level programming language."
        subject            → Python (Entity)
        definitional_relation → "instance-of"
        supertype_lemmas   → ["programming language"]
        modifier_lemmas    → ["high-level"]

    - "Canids are a family of carnivorous mammals."
        subject            → Canidae (Entity or generic type)
        definitional_relation → "subclass-of"
        supertype_lemmas   → ["family", "carnivorous mammal"]

Downstream code may decide whether to realize one or several supertypes,
and how to combine modifiers (e.g. as prenominal adjectives, genitives,
or PP modifiers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity


@dataclass
class DefinitionClassificationFrame:
    """
    Definitional / classification relation between an entity and one or more
    supertypes.

    Core identification
    -------------------

    frame_type:
        Stable string used by routers / planners to recognize this
        relation family. For this frame, the canonical value is:

            "rel.definition-classification"

    subject:
        The entity being defined or classified.

        In encyclopedic contexts this is often the article subject
        (person, place, organization, work, etc.). It should be a fully
        populated :class:`semantics.types.Entity`, including at least a
        `name` and (ideally) a stable `id` (e.g. Wikidata QID).

    Definitional relation
    ---------------------

    definitional_relation:
        High-level label describing the semantic relation between the
        subject and the supertype(s). Recommended values include:

            "instance-of"  – subject is an instance of the type
                             (e.g. Douglas Adams → writer)
            "subclass-of"  – subject is a subtype / subclass
                             (e.g. canids → mammals)
            "role-of"      – subject is a role (e.g. "prime minister")
            "alias-of"     – subject is an alias / alternative name
                             (used rarely in surface text)

        This field is intended for planning / template selection; most
        realizations of "instance-of" and "subclass-of" look similar
        in many languages, but some pipelines may want to distinguish
        them.

    Type and modifiers
    ------------------

    supertype_entities:
        Optional list of supertypes modeled as :class:`Entity`
        instances. This is useful when the supertype itself has a
        Wikidata-style ID or is the subject of its own article
        (e.g. "programming language", "city", "political party").

        Engines can use either `supertype_entities` or
        `supertype_lemmas` (or both) depending on what is available
        in the lexicon.

    supertype_lemmas:
        Lemma-level labels for the type(s) that the subject belongs to,
        for example:

            ["writer"]
            ["programming language"]
            ["political party"]
            ["city", "municipality"]

        These are language-neutral lemma identifiers; how many
        supertypes are realized and how they are coordinated is the
        responsibility of the NLG layer.

    modifier_lemmas:
        Additional lemma-level modifiers that refine the classification,
        for example:

            ["british"]
            ["fictional"]
            ["roman catholic"]
            ["high-level", "general-purpose"]

        These will typically be realized as prenominal adjectives or
        similar constructions depending on language-specific rules.

    gloss:
        Optional short textual gloss or definition snippet that can be
        used as a fallback when insufficient structured classification
        data is available. This may be a language-specific string and
        should be treated as an override / last resort, not the primary
        semantic representation.

    Extension fields
    ----------------

    attributes:
        Arbitrary structured attributes related to this definitional
        fact, using JSON-friendly values. Examples:

            {
                "source": "wikidata",
                "source_property": "P31",
                "confidence": 0.98
            }

        Engines and planners should not rely on any particular keys
        here, but they can inspect them for debugging or advanced
        heuristics.

    extra:
        Free-form metadata bag that is passed through unchanged.
        Intended for provenance, debugging, or links back to the
        original upstream data. Not interpreted by language-neutral
        NLG logic.
    """

    # Stable label used for routing and schema identification
    frame_type: ClassVar[str] = "rel.definition-classification"

    # Core participants
    subject: Entity

    # Relation and classification
    definitional_relation: str = "instance-of"
    supertype_entities: List[Entity] = field(default_factory=list)
    supertype_lemmas: List[str] = field(default_factory=list)
    modifier_lemmas: List[str] = field(default_factory=list)

    # Optional textual fallback
    gloss: Optional[str] = None

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["DefinitionClassificationFrame"]
