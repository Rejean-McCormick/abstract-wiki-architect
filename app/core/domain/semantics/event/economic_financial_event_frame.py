# semantics\event\economic_financial_event_frame.py
"""
semantics/event/economic_financial_event_frame.py
-------------------------------------------------

Semantic frame for economic and financial events.

This module provides a thin, typed wrapper around the generic
:class:`semantics.types.Event` to represent:

    - financial / banking crises
    - bubbles and crashes
    - mergers and acquisitions
    - IPOs and major listings
    - bailouts and rescues
    - sanctions episodes and embargoes

It is intended for higher-level NLG and planning components that need a
structured, language-independent representation of economic or
financial episodes, while keeping the core event semantics in the
underlying :class:`Event` object.

Relationship to the core event model
====================================

At runtime, the *primary* semantic object is ``main_event``:

    - ``main_event.event_type`` should be a controlled label such as
      ``"financial_crisis"``, ``"stock_market_crash"``, ``"merger"``,
      ``"ipo"``, ``"sanctions_episode"``, etc.
    - ``main_event.participants`` encodes role-labelled entities
      involved in the event, for example:

        .. code-block:: python

            main_event.participants = {
                "acquirer": Entity(...),
                "target": Entity(...),
                "regulator": Entity(...),
                "market": Entity(...),
            }

    - ``main_event.time`` and ``main_event.location`` hold the temporal
      and spatial span of the event.
    - ``main_event.properties`` can hold fine-grained values such as:

        .. code-block:: python

            main_event.properties = {
                "deal_value": {"amount": 5000000000.0, "currency": "USD"},
                "index_drop_pct": 7.5,
                "gdp_change_pct": -3.2,
            }

The :class:`EconomicFinancialEventFrame` adds a small number of
specialized, typed fields that are common across many economic /
financial events (affected economies, regulators, sector labels, a
headline monetary amount), plus an open-ended ``attributes`` bag for
other features.

Example usage
=============

    from semantics.types import Entity, Event, TimeSpan, Location
    from semantics.event.economic_financial_event_frame import (
        EconomicFinancialEventFrame,
    )

    crisis_event = Event(
        id="E2008",
        event_type="financial_crisis",
        time=TimeSpan(start_year=2007, end_year=2009),
        location=Location(id="L1", name="global", kind="region"),
        participants={
            "affected_economy": Entity(id="Q30", name="United States"),
            "regulator": Entity(id="Q47551", name="Federal Reserve"),
        },
        properties={
            "gdp_change_pct": -2.8,
            "unemployment_peak_pct": 10.0,
        },
    )

    frame = EconomicFinancialEventFrame(
        main_event=crisis_event,
        subject_entities=[
            Entity(id="Q30", name="United States", entity_type="country"),
        ],
        affected_economies=[
            Entity(id="Q30", name="United States", entity_type="country"),
            Entity(id="Q183", name="Germany", entity_type="country"),
        ],
        regulators=[
            Entity(id="Q47551", name="Federal Reserve"),
        ],
        market_or_sector_labels=["banking", "housing", "global finance"],
        headline_amount=700000000000.0,
        headline_currency="USD",
        headline_amount_year=2008,
    )

Downstream components can use these fields to build sentences such as:

    - "The 2008 financial crisis was a global financial crisis affecting
      the United States and Europe, leading to a USD 700 billion bailout."

Semantics vs. surface form
==========================

This module is **purely semantic**:

    - No language-specific morphology or word order is handled here.
    - Lemmas, labels, and numbers are stored in a neutral form; NLG
      engines decide how to lexicalize them in each language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Event


@dataclass
class EconomicFinancialEventFrame:
    """
    Semantic frame for economic and financial events.

    Core identity
    -------------
    frame_type:
        Stable label for routing / planning. For this family we use
        ``"event.economic"`` to distinguish it from other event and
        relation frames.

    main_event:
        The underlying :class:`Event` instance that carries the core
        semantic structure (participants, time, location, properties).
        Typical ``event_type`` values include:

            - ``"financial_crisis"``
            - ``"stock_market_crash"``
            - ``"merger"``, ``"acquisition"``
            - ``"ipo"``, ``"listing"``
            - ``"bailout"``, ``"rescue_package"``
            - ``"sanctions_episode"``, ``"embargo"``

    label:
        Optional human-readable label for the event (e.g. "2008 global
        financial crisis", "Acme–Globex merger"). This is useful when
        the event is also the subject of an article or section.

    Participants and actors
    -----------------------
    subject_entities:
        High-level entities that are conceptually "about" this event in
        an encyclopedic sense. For a crisis, these might be affected
        countries or regions; for a merger, the companies involved.

    affected_economies:
        Economies, regions, or countries whose macroeconomic indicators
        are impacted (e.g. GDP, unemployment, inflation). These will
        often overlap with ``subject_entities``, but are provided
        separately to make it easier to express sentences such as
        "affecting many European economies".

    regulators:
        Regulatory bodies, central banks, or supranational institutions
        involved in managing or responding to the event (e.g. "Federal
        Reserve", "European Central Bank", "IMF").

    counterparties:
        Additional entities involved as explicit counterparties, useful
        especially for mergers, acquisitions, bailouts, and sanctions
        episodes (e.g. the acquirer and target companies, sender and
        target of sanctions).

    market_or_sector_labels:
        Free-form labels for markets or sectors primarily involved, such
        as ``["banking", "housing", "sovereign debt"]`` or
        ``["tech", "equity markets"]``. These are lemma-like strings,
        not language-specific surface forms.

    Headline magnitude
    ------------------
    headline_amount:
        A single "headline" monetary amount associated with the event,
        such as the value of a merger, the size of a bailout, or the
        volume of assets written down. This is deliberately simple; more
        detailed breakdowns should go into ``attributes`` or
        ``main_event.properties``.

    headline_currency:
        Currency code or label corresponding to ``headline_amount``
        (e.g. ``"USD"``, ``"EUR"``).

    headline_amount_year:
        Reference year for ``headline_amount`` (e.g. deal year or the
        year in which the bailout was announced). This makes it easier
        to generate phrases such as "a USD 50 billion bailout in 2009".

    attributes:
        Open-ended attribute map for additional structured facts, such
        as:

            - index changes (e.g. ``"index_drop_pct"``)
            - macroeconomic indicators (``"gdp_change_pct"``,
              ``"unemployment_peak_pct"``)
            - ratings changes, debt levels, etc.

        Keys and values are project-defined; this dict is intended for
        machine-readable data that may or may not be verbalized.

    extra:
        Arbitrary metadata (e.g. source IDs, original JSON structures,
        debug data) that should not directly affect surface realization.
    """

    # Constant family identifier; excluded from the generated __init__
    frame_type: ClassVar[str] = "event.economic"

    # Core event
    main_event: Event
    label: Optional[str] = None

    # Actors and participants (high-level views over main_event.participants)
    subject_entities: List[Entity] = field(default_factory=list)
    affected_economies: List[Entity] = field(default_factory=list)
    regulators: List[Entity] = field(default_factory=list)
    counterparties: List[Entity] = field(default_factory=list)

    # Domain / sector tags
    market_or_sector_labels: List[str] = field(default_factory=list)

    # Headline monetary magnitude
    headline_amount: Optional[float] = None
    headline_currency: Optional[str] = None
    headline_amount_year: Optional[int] = None

    # Extensibility
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["EconomicFinancialEventFrame"]
