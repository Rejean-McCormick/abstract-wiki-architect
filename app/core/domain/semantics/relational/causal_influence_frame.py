# semantics\relational\causal_influence_frame.py
"""
semantics/relational/causal_influence_frame.py
----------------------------------------------

Relational frame for causal / influence statements of the form:

    - "X caused Y."
    - "X contributed to Y."
    - "X led to Y."
    - "X triggered Y."
    - "X prevented Y."
    - "X enabled Y."

This frame captures a *binary* relation between a cause-side and an
effect-side participant, usually events or state changes, but sometimes
entities (e.g. "the policy", "the law") that stand in for events.

The frame is language-neutral; realization choices (verb selection,
voice, ordering, connectives, hedging) are delegated to downstream
constructions and morphology.

Typical examples
================

    - "The Chernobyl disaster caused widespread radioactive contamination."
        cause  → Chernobyl disaster (Event)
        effect → Radioactive contamination (Event/state)
        causal_relation → "cause"

    - "The Great Depression contributed to the rise of extremism in Europe."
        cause  → Great Depression (Event)
        effect → Rise of extremism in Europe (Event/state)
        causal_relation → "contributes-to"

    - "The treaty prevented further escalation."
        cause  → Treaty (Entity approximating an event / process)
        effect → Further escalation (Event/state)
        causal_relation → "prevents"

Downstream NLG can choose between patterns such as:

    - "X caused Y."
    - "Because of X, Y occurred."
    - "Y was the result of X."
    - "X is thought to have contributed to Y." (using epistemic / hedged
      variants based on the evidence / strength fields).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Union

from semantics.types import Entity, Event, TimeSpan


#: Type alias for convenience: things that can serve as "cause" or "effect".
CauseEffectLike = Union[Entity, Event]


@dataclass
class CausalInfluenceFrame:
    """
    Causal / influence relation between two participants.

    Core identification
    -------------------

    frame_type:
        Stable label used by routers / planners to recognize this
        relational family. For this frame, the canonical value is:

            "rel.causal-influence"

    cause:
        The causal side of the relation: typically an :class:`Event`
        (e.g. "earthquake", "financial crisis", "treaty signing"), but
        can also be an :class:`Entity` when an entity stands in for a
        process (e.g. "the policy", "the treaty", "the organization").

    effect:
        The effect side of the relation: an :class:`Event` or :class:`Entity`
        representing the state / outcome that results from (or is
        influenced by) the cause.

    Relation type and strength
    --------------------------

    causal_relation:
        Coarse label describing the subtype of the causal / influence
        relation. Recommended values include:

            "cause"           – X directly causes Y
            "contributes-to"  – X contributes to or facilitates Y
            "leads-to"        – X leads to Y (often over time)
            "triggers"        – X immediately triggers Y
            "enables"         – X enables Y (makes Y possible)
            "prevents"        – X prevents Y
            "associated-with" – correlation or non-directional linkage

        This field mainly guides verb choice and possible hedging in
        surface text; its inventory is project-specific.

    polarity:
        Optional high-level polarity of the effect from the perspective
        of the article subject or narrator. Typical values:

            "positive" | "negative" | "mixed" | "neutral"

        This is *not* required for grammaticality, but may be used
        in more opinion-sensitive domains or for shaping discourse.

    strength:
        Optional numerical strength of the relationship, in whatever
        scale a project chooses (e.g. 0.0–1.0, or 1–5). Engines should
        treat this as advisory metadata and not rely on any particular
        scaling convention.

    Temporal / scope hints
    ----------------------

    time:
        Optional :class:`TimeSpan` indicating when the causal influence
        is understood to hold, or when the effect occurred.

    scope_description:
        Free-form textual hint describing the scope / domain of the
        influence, e.g.:

            "in Europe"
            "on global temperature"
            "on the local economy"

        Where possible, prefer structured representations (e.g. attach
        regions as Locations to the underlying Events), but this is
        provided as a pragmatic escape hatch.

    Mechanism and evidence
    ----------------------

    mechanism_lemmas:
        Lemma-level description of the mechanism or pathway of influence,
        such as:

            ["economic", "political"]
            ["through trade", "through migration"]

        These are language-neutral hints that can be mapped to surface
        phrases in constructions.

    mechanism_gloss:
        Optional short textual gloss explaining the mechanism in more
        detail (language-specific, used only when engines choose to
        surface it explicitly).

    evidence:
        Optional structured evidence / provenance information, using a
        JSON-friendly dictionary. Typical keys might include:

            {
                "source": "IPCC AR6",
                "source_type": "report",
                "confidence": 0.9,
                "citation_keys": ["Smith2020", "Doe2018"]
            }

        NLG components should treat this as opaque metadata; decisions
        about whether and how to verbalize evidence are project-specific.

    Generic extension points
    ------------------------

    attributes:
        Arbitrary structured attributes related to this causal relation,
        beyond the basic fields above. Examples:

            {
                "reversibility": "irreversible",
                "lag_years": 10
            }

    extra:
        Free-form metadata that is passed through unchanged. Intended
        for provenance, debugging, or links back to original source
        structures (e.g. property IDs, row numbers, raw JSON).
    """

    # Stable label used for routing and schema identification.
    frame_type: ClassVar[str] = "rel.causal-influence"

    # Core participants
    cause: CauseEffectLike
    effect: CauseEffectLike

    # Relation and strength
    causal_relation: str = "cause"
    polarity: Optional[str] = None
    strength: Optional[float] = None

    # Temporal / scope hints
    time: Optional[TimeSpan] = None
    scope_description: Optional[str] = None

    # Mechanism and evidence
    mechanism_lemmas: List[str] = field(default_factory=list)
    mechanism_gloss: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Generic extension points
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["CausalInfluenceFrame"]
