# semantics\entity\discipline_theory_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, TimeSpan


@dataclass
class DisciplineTheoryFrame:
    """
    Academic discipline / field / theory frame.

    High-level semantic frame for Wikipedia-style summaries of **academic
    disciplines, scientific fields, subfields, schools of thought, and named
    theories**.

    The goal is to capture enough structure to support sentences such as:

        - "Topology is a branch of mathematics concerned with the properties
          of space that are preserved under continuous transformations."
        - "Cognitive science is an interdisciplinary field that studies the
          mind and its processes."
        - "General relativity is a theory of gravitation developed by
          Albert Einstein."

    This frame is deliberately **language-agnostic** and contains no surface
    strings beyond neutral lemmas. All language-specific realization happens
    downstream (lexicon + constructions + family engines).

    Core conventions
    ----------------
    * The discipline / theory being described is always `main_entity`.
    * Coarse categorization is stored in `discipline_kind`.
    * Taxonomic relations to other disciplines use `parent_disciplines` and
      `subdisciplines`.
    * Conceptual and historical context (core concepts, applications,
      influences, key figures) use lemmas and `Entity` references.

    Fields
    ------
    frame_type:
        Constant string identifier for this frame family: `"discipline-theory"`.
        Used for debugging and routing.

    main_entity:
        The discipline, field, subfield, school of thought, or named theory
        the article / summary is about. Typically an `Entity` with
        `entity_type` set to something like `"academic_discipline"`,
        `"scientific_field"`, `"theory"`, `"school_of_thought"`, etc.

    discipline_kind:
        Optional coarse label describing what kind of conceptual entity this
        is, e.g.:

            - "academic_discipline"
            - "scientific_field"
            - "subfield"
            - "interdisciplinary_field"
            - "theory"
            - "hypothesis"
            - "school_of_thought"

        Left as a free string so projects can define their own inventory.
        Often mirrors or refines `main_entity.entity_type`.

    parent_disciplines:
        List of broader or parent disciplines, represented as `Entity`
        objects, e.g.:

            - mathematics
            - physics
            - psychology
            - philosophy

        These support sentences like "Topology is a branch of mathematics"
        or "Cognitive science is an interdisciplinary field drawing on
        psychology, linguistics, and computer science."

    subdisciplines:
        List of subdisciplines / subfields / specializations that are
        commonly treated as parts of this discipline. This can be used in
        multi-sentence descriptions or lists.

    origin_timespan:
        `TimeSpan` indicating when the discipline or theory emerged as
        a distinct concept or field (e.g. approximate centuries or decades).
        For ongoing development, this may be a range.

    origin_region_lemmas:
        Neutral lemmas describing the main cultural / geographic regions
        associated with the origin (e.g. ["europe"], ["ancient_greece"],
        ["united_states"]). These are keys for lexicon / realization, not
        surface strings.

    key_figures:
        Prominent people associated with the discipline or theory, represented
        as `Entity` objects (e.g. "Albert Einstein", "Noam Chomsky").
        These can be used to generate sentences like "Key figures include ...".

    core_concept_lemmas:
        Lemmas naming central concepts, constructs, or topics of the field,
        e.g. ["manifold", "continuous_function", "metric_space"] for topology,
        or ["attention", "memory", "perception"] for cognitive science.
        Downstream, these can be selectively realized in definitions or lists.

    applications_lemmas:
        Lemmas describing major application areas of the discipline /
        theory (e.g. ["engineering"], ["medicine"], ["artificial_intelligence"],
        ["economics"]). These support text such as "with applications in ...".

    schools_traditions_lemmas:
        Lemmas naming major internal schools, traditions, or approaches,
        e.g. ["behaviorism"], ["structuralism"], ["functionalism"], or
        sub-approaches to a theory. These are optional and often used only
        for longer descriptions.

    influenced_disciplines:
        List of disciplines / fields that this discipline or theory has
        significantly influenced, as `Entity` objects. Suitable for sentences
        like "The theory has influenced X and Y."

    influenced_by:
        List of disciplines / theories / schools that influenced the
        emergence or development of `main_entity`. Similar to
        `influenced_disciplines` but in the opposite direction.

    attributes:
        Additional, structured properties that do not justify their own
        fields. Example conventional keys:

            {
                "primary_domain_lemmas": ["natural_sciences"],
                "secondary_domain_lemmas": ["engineering"],
                "typical_degree_levels": ["bachelor", "master", "phd"],
                "classification_codes": {
                    "msc_2020": ["57-XX"],
                    "j_el_classification": ["C1"],
                },
            }

        Use this for metadata that might occasionally appear in text but
        is mostly for infoboxes / structured use.

    extra:
        Arbitrary metadata, typically used for provenance or storing the
        original source representation. Examples:

            {
                "wikidata_qid": "Q12345",
                "aw_raw": {...},   # original Abstract Wikipedia / Ninai frame
                "notes": "merged from multiple sources"
            }

        This field should not affect semantics directly; it is mainly for
        debugging, round-tripping, and translation back to upstream schemas.
    """

    # Constant family identifier; not included in __init__.
    frame_type: ClassVar[str] = "discipline-theory"

    # Core identity
    main_entity: Entity

    # Classification
    discipline_kind: Optional[str] = None

    # Taxonomic relations
    parent_disciplines: List[Entity] = field(default_factory=list)
    subdisciplines: List[Entity] = field(default_factory=list)

    # Historical and geographic origin
    origin_timespan: Optional[TimeSpan] = None
    origin_region_lemmas: List[str] = field(default_factory=list)

    # People and concepts
    key_figures: List[Entity] = field(default_factory=list)
    core_concept_lemmas: List[str] = field(default_factory=list)
    applications_lemmas: List[str] = field(default_factory=list)
    schools_traditions_lemmas: List[str] = field(default_factory=list)

    # Influence relations
    influenced_disciplines: List[Entity] = field(default_factory=list)
    influenced_by: List[Entity] = field(default_factory=list)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["DisciplineTheoryFrame"]
