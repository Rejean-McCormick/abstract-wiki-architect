# semantics\entity\creative_work_frame.py
"""
semantics/entity/creative_work_frame.py
---------------------------------------

Semantic frame for creative works (books, films, TV series, albums, songs,
paintings, video games, etc.).

The goal of this module is to provide a *language-agnostic* data structure
that upstream code (bridges, CSV/JSON loaders, Wikidata adapters) can fill
from loosely-structured data. The NLG pipeline can then pick suitable
constructions for first-sentence / short-summary descriptions.

This frame is intentionally generic: it does not hard-code a fine-grained
ontology of work types or contributor roles. Instead, it uses free-form
strings (e.g. ``"film"``, ``"novel"``, ``"director"``, ``"author"``)
so that different projects can define their own inventories if desired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event, TimeSpan


# ---------------------------------------------------------------------------
# Contributor / credit information
# ---------------------------------------------------------------------------


@dataclass
class CreativeWorkContributor:
    """
    A person or organization credited for a creative work.

    This is a thin wrapper around :class:`semantics.types.Entity` that
    adds a role label and a few common metadata slots.

    Typical examples::

        CreativeWorkContributor(
            entity=Entity(name="Hayao Miyazaki", human=True, entity_type="person"),
            role="director",
        )

        CreativeWorkContributor(
            entity=Entity(name="Studio Ghibli", entity_type="organization"),
            role="production_company",
        )

    Fields
    ------
    entity:
        The contributor entity (person, organization, collective, ...).

    role:
        Free-form role label describing how the entity contributed to the
        work. Examples (non-exhaustive):

        * "author", "co_author"
        * "editor"
        * "director"
        * "screenwriter"
        * "producer", "executive_producer"
        * "composer"
        * "performer", "lead_actor", "voice_actor"
        * "studio", "publisher", "label"

        Downstream code may normalize these to a controlled vocabulary.

    credited_as:
        Optional credit string if it differs from the entity's canonical
        ``name`` (e.g. stage name, pen name, or specific billing).

    extra:
        Arbitrary metadata, e.g. billing order, episode-specific notes,
        original data structure from a source system, etc.
    """

    entity: Entity
    role: str
    credited_as: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main creative work frame
# ---------------------------------------------------------------------------


@dataclass
class CreativeWorkFrame:
    """
    High-level semantic frame for a creative work.

    This frame is meant to support Wikipedia-style lead sentences such as:

        - "Inception is a 2010 science fiction film written and directed
          by Christopher Nolan."
        - "Pride and Prejudice is an 1813 novel by Jane Austen."
        - "The Beatles' Abbey Road is a 1969 studio album released by
          Apple Records."
        - "The Starry Night is an oil-on-canvas painting by Vincent van Gogh."

    Fields
    ------
    main_work:
        Entity representing the work itself. Typically:

        * ``name``  – the canonical title, e.g. "Inception".
        * ``entity_type`` – a coarse hint such as "film", "novel",
          "album", "song", "painting", "game", etc. (optional).
        * ``extra`` – may include IDs (e.g. Wikidata QID) or medium.

    work_kind:
        Optional fine-grained label for the type of work, e.g.:

        * "film", "short_film", "television_series", "episode"
        * "novel", "novella", "short_story", "manga"
        * "album", "single", "song"
        * "painting", "sculpture"
        * "video_game", "board_game"

        This is a free string; different projects can define their own
        controlled lists. If omitted, downstream code may fall back to
        ``main_work.entity_type`` or infer from source metadata.

    contributors:
        List of :class:`CreativeWorkContributor` instances describing
        key creative roles (authors, directors, studios, performers, etc.).

    primary_creator_roles:
        Optional mapping from a *normalized* role name to the subset of
        contributors that should be highlighted in short summaries.

        For example, a loader may populate:

        .. code-block:: python

            primary_creator_roles = {
                "author": ["Q123", "Q456"],
                "director": ["Q789"],
            }

        where the values are contributor entity IDs or some other stable
        key. The exact key type is left open (``Any``) so that different
        bridges can choose what is convenient.

        This mapping is **advisory**: NLG code may consult it when
        deciding which creators to mention first.

    original_release:
        Time span for the first publication / release / premiere
        (e.g. original film release year, novel publication date).
        Represented as :class:`TimeSpan` from :mod:`semantics.types`.

    country_of_origin:
        Optional entity representing the primary country of origin
        of the work (e.g. "United States", "Japan"). This is a regular
        :class:`Entity` with ``entity_type="country"`` in most cases.

    original_language_codes:
        List of BCP-47-ish language codes in which the work originally
        appeared, e.g. ``["en"]``, ``["ja"]``, ``["en", "fr"]``.

        These are *not* target NLG languages; they describe the
        in-universe/original languages of the work.

    genres:
        List of free-form genre labels such as "science fiction",
        "romantic novel", "progressive rock", "first-person shooter".
        These are plain strings; mapping to lexemes is left to the
        calling code or to language-specific resources.

    runtime_minutes:
        Optional running time in minutes for time-based media
        (films, episodes, games), if known.

    number_of_pages:
        Optional page count for text-based works (books, comics, etc.).

    part_of_series:
        Optional entity representing a series, franchise, or shared
        universe the work belongs to (e.g. "The Legend of Zelda",
        "Marvel Cinematic Universe").

    based_on:
        Optional entity representing a source work or underlying
        material (novel, manga, play, etc.). For example, a film
        adaptation may reference the original novel entity here.

    related_events:
        List of salient events associated with the work, modeled as
        :class:`semantics.types.Event`. Typical examples:

        * publication event(s)
        * premieres
        * major awards
        * notable bans / controversies (if expressed as events)

        For simple lead sentences, these may not be needed; they are more
        useful for extended summaries and timelines.

    attributes:
        Arbitrary attribute map for additional facts about the work,
        e.g.:

        .. code-block:: python

            {
                "themes": ["friendship", "war"],
                "target_audience": ["children"],
                "setting_time": "Victorian era",
                "setting_place": "rural England",
            }

        Downstream components can decide which keys they understand.

    extra:
        Free-form metadata bag (source JSON, raw AW structures, IDs).
        This field is never interpreted by the NLG core and is provided
        purely for caller convenience.

    frame_type:
        Stable label identifying this frame family, set to
        ``"creative_work"``. This allows routers that operate on
        generic ``Frame`` objects to dispatch on ``frame.frame_type``.
    """

    # Main subject of the frame
    main_work: Entity

    # High-level categorization
    work_kind: Optional[str] = None

    # Contributors / credits
    contributors: List[CreativeWorkContributor] = field(default_factory=list)

    # Advisory "primary" creators, keyed by normalized role label
    primary_creator_roles: Dict[str, List[Any]] = field(default_factory=dict)

    # Publication / release / origin info
    original_release: Optional[TimeSpan] = None
    country_of_origin: Optional[Entity] = None
    original_language_codes: List[str] = field(default_factory=list)

    # Descriptive attributes
    genres: List[str] = field(default_factory=list)
    runtime_minutes: Optional[int] = None
    number_of_pages: Optional[int] = None

    # Relations to other works / entities
    part_of_series: Optional[Entity] = None
    based_on: Optional[Entity] = None

    # Associated events (awards, premieres, etc.)
    related_events: List[Event] = field(default_factory=list)

    # Generic attribute and metadata bags
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # Frame protocol hook (not included in __init__ signature)
    frame_type: str = field(init=False, default="creative_work")


__all__ = [
    "CreativeWorkContributor",
    "CreativeWorkFrame",
]
