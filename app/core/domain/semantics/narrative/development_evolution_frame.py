# semantics\narrative\development_evolution_frame.py
"""
semantics/narrative/development_evolution_frame.py
==================================================

Narrative / aggregate frame for development and evolution over time.

This module defines a semantic frame for describing how a single subject
(e.g. a city, a product, an organization, a theory) changes over time in
a small number of phases or stages. Typical encyclopedic uses include:

    - "The city grew from a small trading post into a major industrial centre."
    - "The theory evolved through several revisions during the 20th century."
    - "The company gradually shifted from hardware to cloud services."

The frame is **aggregate / narrative**:

    - It is not a single event, but a structured summary composed of
      stages, transitions, and driving factors.
    - It sits on top of lower-level :class:`Event` objects where
      available, but does not require them; coarse-grained stages with
      approximate time spans are often sufficient.

The concrete lexical and syntactic realization (e.g. tense/aspect,
connectives like "initially", "later", "by the 1990s") is handled by NLG
engines and constructions. This module only defines the abstract data
shape those components can rely on.

Relationship to frame inventory
-------------------------------

In :mod:`semantics.all_frames`, this frame corresponds to the
``"aggregate.development"`` frame type (item 51 in the global inventory
of frame families).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan


@dataclass
class DevelopmentStage:
    """
    A single stage or phase in the development / evolution of a subject.

    Stages are intentionally coarse-grained; most real-world narratives
    only need a handful of them (e.g. "founding and early growth",
    "industrialization", "post-war expansion", "post-2000 restructuring").

    Fields
    ------

    label:
        Short, language-neutral label for the stage, e.g.:

            - "founding_and_early_growth"
            - "industrialization"
            - "digital_transformation"

        This is typically used for planning / debugging; engines may
        map it to more natural surface phrases.

    time_span:
        Optional :class:`TimeSpan` giving the approximate temporal
        extent of the stage (years or decades are usually sufficient).

    summary:
        Optional short, language-neutral description of what characterizes
        this stage, suitable as a paraphrasable key idea. For example:

            - "rapid urbanization and industrial growth"
            - "transition from state planning to market economy"

        The string is not expected to be final output in any language;
        it acts as a semantic hint that can be rephrased.

    key_events:
        Optional list of :class:`Event` instances that anchor the stage,
        such as:

            - founding / incorporation events,
            - major reforms,
            - wars, crises, or major discoveries.

        Engines can choose to mention some of these explicitly or use
        them only for temporal / causal structuring.

    drivers:
        Optional list of language-neutral labels for forces or drivers
        behind this stage, such as:

            - "industrialization"
            - "technological_innovation"
            - "policy_reform"
            - "globalization"

        These can be used for constructions like "driven by X and Y".
    """

    label: str
    time_span: Optional[TimeSpan] = None
    summary: Optional[str] = None
    key_events: List[Event] = field(default_factory=list)
    drivers: List[str] = field(default_factory=list)


@dataclass
class DevelopmentEvolutionFrame:
    """
    Aggregate frame for the development / evolution of a single subject.

    This frame captures how a subject (city, state, organization,
    product, theory, etc.) changes over time, organized into stages with
    optional key events and drivers.

    It is intended to support paragraph-level or section-level
    summaries, but can also be used to generate a concise single
    sentence when only a few stages are provided.

    Core identity
    -------------

    frame_type:
        Stable frame-type identifier for routing and introspection.
        For this frame family it is fixed to ``"aggregate.development"``.

    subject:
        The entity whose development / evolution is being described.
        This is usually the same as the article's main subject
        (e.g. the city, organization, or concept), represented as an
        :class:`Entity`.

    overall_time_span:
        Optional coarse :class:`TimeSpan` covering the full period of
        development described by this frame. This may be broader than
        the union of all stage time spans.

    Stages and transitions
    ----------------------

    stages:
        Ordered list of :class:`DevelopmentStage` instances, representing
        successive phases in the subject's development. The ordering is
        chronological, from earliest to latest.

        Not all narratives require many stages; two or three are often
        enough for a compact encyclopedic summary.

    key_transitions:
        Optional list of :class:`Event` instances representing specific
        transition points between stages (e.g. a reform, a merger, a
        crisis that marks the boundary between "early growth" and
        "restructuring").

        Engines can use these to choose constructions like "After X,
        the city entered a period of Y".

    Global drivers and outcomes
    ---------------------------

    global_drivers:
        Optional list of language-neutral labels for overarching drivers
        of the subject's development, at a higher level than the per-
        stage `drivers`. Examples:

            - "colonization"
            - "industrialization"
            - "post-war_reconstruction"
            - "digitalization"

    global_outcomes:
        Optional list of language-neutral labels for key outcomes or
        end states of the development, such as:

            - "major_industrial_centre"
            - "global_tech_hub"
            - "declining_population"

        These may be realized in constructions like "and today it is
        X" or "ultimately becoming Y".

    Extensibility
    -------------

    attributes:
        Open-ended dictionary for additional structured facts or
        numeric indicators, for example:

            {
                "population_change": {
                    "start_year": 1900,
                    "end_year": 2020,
                    "factor": 10.5
                },
                "gdp_growth_pattern": "rapid_then_stable"
            }

        Keys and values are project-defined and may or may not be
        verbalized.

    extra:
        Opaque metadata (e.g. original JSON, provenance, debug
        information) preserved from upstream systems. Not intended to
        be interpreted by the generic NLG layer.
    """

    # Stable identifier for this frame family, for routing / introspection.
    frame_type: str = field(init=False, default="aggregate.development")

    # Core subject and temporal scope
    subject: Entity
    overall_time_span: Optional[TimeSpan] = None

    # Internal structure of the development
    stages: List[DevelopmentStage] = field(default_factory=list)
    key_transitions: List[Event] = field(default_factory=list)

    # Global drivers / outcomes
    global_drivers: List[str] = field(default_factory=list)
    global_outcomes: List[str] = field(default_factory=list)

    # Extensibility
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["DevelopmentStage", "DevelopmentEvolutionFrame"]
