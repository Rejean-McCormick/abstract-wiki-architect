# semantics\event\election_referendum_event_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


@dataclass
class CandidateResult:
    """
    Result row for an individual candidate or list in an election.

    This helper type is intentionally small and data-oriented. It is meant to
    capture the most common comparative facts that show up in encyclopedic
    descriptions of elections:

        - who ran,
        - how many votes they received,
        - what share of the vote that represents,
        - whether they were elected and/or how many seats they obtained.

    Fields
    ------

    candidate:
        The candidate, party, or list being evaluated. In many real-world
        cases this will be a political party or alliance rather than a single
        person, but the frame keeps this generic and relies on `Entity`.

    party:
        Optional party or alliance for the candidate when `candidate` is a
        person. May be left `None` if `candidate` already denotes a party.

    votes:
        Absolute number of votes received, if available.

    vote_share:
        Fraction of valid votes obtained, represented as a float between 0.0
        and 1.0 (e.g. 0.52 for 52%). Percentage-style representations are left
        to the realization layer.

    seats:
        Number of seats obtained in a legislature, if applicable (for
        parliamentary elections or list systems).

    outcome:
        Coarse-grained outcome label, typically values such as:

            - "elected"
            - "re_elected"
            - "runner_up"
            - "eliminated"
            - "no_seats"

        The inventory is intentionally open; upstream code may normalize or
        constrain values.

    extra:
        Open-ended map for additional result metadata (e.g. "swing",
        "rank_in_round_1", etc.).
    """

    candidate: Entity
    party: Optional[Entity] = None

    votes: Optional[int] = None
    vote_share: Optional[float] = None
    seats: Optional[int] = None

    outcome: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferendumOptionResult:
    """
    Result row for a choice in a referendum.

    This is structurally analogous to `CandidateResult` but tailored to
    yes/no or option-based referendums rather than candidate races.

    Fields
    ------

    label:
        Short label for the option, e.g. "yes", "no", "remain", "leave",
        "proposal", "counterproposal". This is a lemma-level label; surface
        realization is left to the generation layer.

    votes:
        Absolute number of votes for the option, if available.

    vote_share:
        Fraction of valid votes obtained, represented as a float between 0.0
        and 1.0.

    outcome:
        Coarse-grained outcome label such as "approved", "rejected",
        "majority", "minority". The inventory is open-ended.

    extra:
        Open-ended map for additional metadata (e.g. "qualified_majority_met",
        "turnout_threshold_met").
    """

    label: str

    votes: Optional[int] = None
    vote_share: Optional[float] = None

    outcome: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ElectionReferendumEventFrame:
    """
    Event frame for elections and referendums.

    This frame family corresponds to the `frame_type = "event.election"`
    entry in the global taxonomy of frame families. It is intended for
    standalone articles about electoral events as well as embedded summaries
    inside biographies, timelines, or project frames.

    Design
    ------

    * Semantics is language-neutral and compact.
    * Fine-grained numerical details live in small helper records
      (`CandidateResult`, `ReferendumOptionResult`) and open-ended maps
      (`properties`, `extra`).
    * The structure is compatible with the generic `Event` semantics described
      in `docs/FRAMES_EVENT.md`:

        - `time`  ↔  `TimeSpan`
        - `location`  ↔  `Location`
        - participants such as winners/candidates are represented as `Entity`
          instances and their per-candidate metrics via `CandidateResult`.

    This frame does **not** attempt to model every possible electoral
    institution. It focuses on what is typically expressed in lead paragraphs:

        - what kind of election or referendum it was,
        - for which office/body and in which jurisdiction,
        - when and where it took place,
        - who won, and key numerical highlights (turnout, vote shares, seats).

    Fields
    ------

    frame_type:
        Stable identifier for this family. Always "event.election".
        Exposed so that the NLG router and normalization layer can dispatch
        correctly.

    id:
        Optional stable identifier for the event, typically a Wikidata ID
        or upstream knowledge-base handle.

    event_kind:
        Coarse classification of the event within this family, typically:

            - "election"
            - "referendum"

        The value is intentionally open; more specific strings like
        "presidential_election", "parliamentary_election",
        "constitutional_referendum" are also allowed.

    office:
        Target office for the election (e.g. "President", "Mayor of X") as an
        `Entity`. May be `None` for purely legislative/list elections or
        multi-office ballots.

    body:
        Representative body being elected when applicable (e.g. "House of
        Commons", "Bundestag", "City Council"). Often used for parliamentary
        elections.

    jurisdiction:
        Main jurisdiction in which the election or referendum took place,
        typically a `geopolitical-entity` such as a country, state, or city.

    supervising_body:
        Electoral commission or similar authority responsible for overseeing
        the vote.

    time:
        Date or interval when the vote took place, represented as a `TimeSpan`.

    location:
        Main physical location, when a specific city/venue is salient (e.g.
        for a party leadership election held at a congress). For nationwide
        votes this may be left `None` or limited to the capital.

    electoral_system:
        Short description of the voting system, e.g.:

            - "first_past_the_post"
            - "two_round"
            - "proportional_representation"
            - "mixed_member_proportional"

        The inventory is project-specific and loosely constrained.

    chamber_size:
        Total number of seats in the elected body, if applicable.

    seats_contested:
        Number of seats up for election in this event (may be less than or
        equal to `chamber_size` for partial renewals).

    electorate_size:
        Number of eligible voters, if known.

    total_votes:
        Total number of votes cast (valid + invalid) if known.

    turnout_absolute:
        Number of participating voters (can be equal to `total_votes` in
        simple counts).

    turnout_rate:
        Turnout as a fraction of the eligible electorate, represented as a
        float between 0.0 and 1.0.

    main_parties:
        Coarse list of main parties or alliances involved in the election.

    candidate_results:
        Detailed per-candidate (or per-list) results, ordered arbitrarily or
        by votes. For single-winner elections this typically includes the
        winner and one or more runners-up; for list systems, parties or lists.

    referendum_question:
        For referendums, the abstract/lemma-level question or topic being
        voted on, e.g. "membership of the European Union",
        "approval of the new constitution". Surface-level formulation is
        handled downstream.

    referendum_option_results:
        Detailed per-option results for referendums (e.g. yes/no, leave/remain).

    winning_entities:
        Convenience list of winning candidates/parties/options as `Entity`
        instances, for quick access by generators or other frames.

    properties:
        Open-ended map for additional structured attributes that are not yet
        modeled as first-class fields (e.g. "rounds", "coalition_formed",
        "thresholds", "age_limit", "compulsory_voting": true).

    extra:
        Free-form metadata and provenance (e.g. original Z-objects, raw
        statement IDs, notes for debugging). Not interpreted by the NLG layer.
    """

    # Frame protocol discriminator
    frame_type: ClassVar[str] = "event.election"

    # Core identity
    id: Optional[str] = None
    event_kind: Optional[str] = None  # "election", "referendum", ...

    # Institutional context
    office: Optional[Entity] = None
    body: Optional[Entity] = None
    jurisdiction: Optional[Entity] = None
    supervising_body: Optional[Entity] = None

    # Time and place
    time: Optional[TimeSpan] = None
    location: Optional[Location] = None

    # Electoral mechanics
    electoral_system: Optional[str] = None
    chamber_size: Optional[int] = None
    seats_contested: Optional[int] = None

    # Turnout and aggregates
    electorate_size: Optional[int] = None
    total_votes: Optional[int] = None
    turnout_absolute: Optional[int] = None
    turnout_rate: Optional[float] = None  # 0.0–1.0

    # Actors and results
    main_parties: List[Entity] = field(default_factory=list)
    candidate_results: List[CandidateResult] = field(default_factory=list)

    # Referendum-specific fields
    referendum_question: Optional[str] = None
    referendum_option_results: List[ReferendumOptionResult] = field(
        default_factory=list
    )

    # Convenience summary
    winning_entities: List[Entity] = field(default_factory=list)

    # Extensibility hooks
    properties: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    "ElectionReferendumEventFrame",
    "CandidateResult",
    "ReferendumOptionResult",
]
