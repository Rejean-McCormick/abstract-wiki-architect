# semantics\event\historical_event_frame.py
# semantics/event/historical_event_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event


@dataclass
class HistoricalEventFrame:
    """
    Historical / political event frame.

    High-level semantic frame for Wikipedia-style summaries of **historical
    and political events** such as revolutions, coups, reforms, constitutional
    changes, and other major transitions of power or governance.

    The frame is a thin, family-specific wrapper around :class:`semantics.types.Event`.
    The intent is to:

        * mark the frame as belonging to the ``"event.historical"`` family
          for routing / engine selection; and
        * provide a small number of conventional, high-level slots that are
          convenient for NLG engines and upstream normalization.

    Core conventions
    ----------------

    * The **subject of the article / description** is always ``main_event``.
    * Most low-level event structure (participants, time, location, properties)
      lives inside the :class:`Event` instance.
    * This wrapper focuses on:

        - a focal entity (often the country / regime most affected),
        - coarse cause / outcome descriptors, and
        - optional sub-events (precursors, aftermath).

    Fields
    ------

    main_event:
        The core :class:`Event` object representing the historical event
        itself. This is expected to carry:

            - ``event_type`` and more specific subtypes, e.g.
              ``"revolution"``, ``"coup_d_etat"``, ``"constitutional_reform"``;
            - participant roles (government, opposition, foreign powers, etc.);
            - temporal information (start / end times, key dates);
            - primary location information.

    focal_entity:
        Optional :class:`Entity` representing the main entity whose history is
        being described from the point of view of this event. Typical examples:

            - the country or polity undergoing the transition,
            - a regime or government that comes to power / is overthrown,
            - an organization that is central to the event.

        Engines can use this to choose subject / topic in text such as:

            "The French Revolution was a period of far-reaching social and
             political change in France."

    short_label:
        Optional short textual label or lemma-like summary of the event
        family, e.g. ``"revolution"``, ``"coup"``, ``"independence"``.
        This is a hint for realization and is not required.

    cause_lemmas:
        Optional list of coarse cause descriptors in lemma form, such as:

            ["economic_crisis"]
            ["election_dispute"]
            ["colonial_rule"]

        Intended for high-level summaries ("triggered by an economic crisis").

    outcome_lemmas:
        Optional list of coarse outcome descriptors in lemma form, such as:

            ["independence"]
            ["regime_change"]
            ["new_constitution"]

        Intended for phrases like "resulting in X".

    precursor_events:
        Optional list of :class:`Event` objects representing important
        build-up events (e.g. protests, earlier reforms) that may be used in
        timelines or richer multi-sentence descriptions.

    aftermath_events:
        Optional list of :class:`Event` objects representing immediate
        consequences (e.g. subsequent elections, civil wars, peace treaties).

    attributes:
        Additional structured properties that do not justify dedicated fields
        but may be useful to engines or downstream tools. Example keys:

            {
                "ideological_context_lemmas": ["liberalism", "nationalism"],
                "conflict_scale": "national",
                "violence_level": "high",
                "estimated_casualties": 10000,
            }

    extra:
        Arbitrary metadata, typically used for provenance or round-tripping
        to upstream schemas (e.g. raw AbstractWiki blobs, Wikidata IDs).
        This should not affect semantics directly.

    frame_type:
        Canonical family identifier for this frame: ``"event.historical"``.
        Exposed for routing and debugging. It is not included in the
        ``__init__`` signature; callers should not need to set it manually.
    """

    # ------------------------------------------------------------------
    # Core event and context
    # ------------------------------------------------------------------

    #: The event that is the subject of the article / summary.
    main_event: Event

    #: Optional focal entity whose history is being told through this event
    #: (e.g. a country, regime, or major organization).
    focal_entity: Optional[Entity] = None

    #: Optional coarse label / lemma describing the event kind
    #: (e.g. "revolution", "coup", "independence").
    short_label: Optional[str] = None

    # ------------------------------------------------------------------
    # High-level causal and outcome descriptors
    # ------------------------------------------------------------------

    #: Coarse cause descriptors in lemma form.
    cause_lemmas: List[str] = field(default_factory=list)

    #: Coarse outcome descriptors in lemma form.
    outcome_lemmas: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Optional sub-events and structure
    # ------------------------------------------------------------------

    #: Important build-up events leading to the main_event.
    precursor_events: List[Event] = field(default_factory=list)

    #: Immediate aftermath events following the main_event.
    aftermath_events: List[Event] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Generic extension points
    # ------------------------------------------------------------------

    #: Additional structured attributes that do not have dedicated slots.
    attributes: Dict[str, Any] = field(default_factory=dict)

    #: Free-form metadata / provenance bag.
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Frame protocol hook
    # ------------------------------------------------------------------

    #: Stable frame family identifier used by routers / engines.
    frame_type: str = field(init=False, default="event.historical")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Lightweight, explicit dictionary view of the main slots.

        This is intended for debugging, JSON dumps, or lightweight tooling.
        It intentionally keeps a shallow structure and does not attempt to
        recursively serialize nested dataclasses.
        """
        return {
            "frame_type": self.frame_type,
            "main_event": self.main_event,
            "focal_entity": self.focal_entity,
            "short_label": self.short_label,
            "cause_lemmas": list(self.cause_lemmas),
            "outcome_lemmas": list(self.outcome_lemmas),
            "precursor_events": list(self.precursor_events),
            "aftermath_events": list(self.aftermath_events),
            "attributes": dict(self.attributes),
            "extra": dict(self.extra),
        }


__all__ = ["HistoricalEventFrame"]
