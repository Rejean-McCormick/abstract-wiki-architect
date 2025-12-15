# semantics\entity\competition_league_frame.py
"""
semantics/entity/competition_league_frame.py
--------------------------------------------

High-level semantic frame for sports competitions, tournaments, and leagues.

This module defines a typed data class that captures the key fields needed
to generate Wikipedia-style lead sentences and short descriptions for
competitions and leagues, such as:

    - national football leagues (e.g. "Premier League")
    - international tournaments (e.g. "UEFA Champions League")
    - seasonal competitions (e.g. "2019–20 Premier League")

The frame is intentionally *semantic* and language-neutral; it does not
encode any surface realization details. Those are delegated to:

    - semantics.aw_bridge (for converting loose JSON / AW-style dicts to
      this frame), and
    - the constructions / morphology layer (for actual sentence generation).

Example usage
=============

    from semantics.types import Entity, Location, TimeSpan
    from semantics.entity.competition_league_frame import CompetitionLeagueFrame

    premier_league = Entity(
        id="Q9448",
        name="Premier League",
        entity_type="competition",
    )

    fa = Entity(
        id="Q208030",
        name="The Football Association",
        entity_type="organization",
    )

    england = Location(
        id="Q21",
        name="England",
        kind="country",
        country_code="GB",
    )

    frame = CompetitionLeagueFrame(
        main_entity=premier_league,
        sport_lemma="association football",
        competition_kind="league",
        level="top tier",
        organizing_body=fa,
        host_regions=[england],
        founded=TimeSpan(start_year=1992),
        number_of_teams=20,
        format_summary="round-robin",
    )

A rendering pipeline might then map this to language-specific constructions,
for example (English):

    "The Premier League is the top tier of the English football league system."

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_competition_kind(kind: Optional[str]) -> Optional[str]:
    """
    Normalize a loose competition kind string (“League”, “league competition”)
    into a small canonical inventory.

    Current canonical values (you can extend this as needed):

        - "league"
        - "cup"
        - "tournament"
        - "championship"
        - "season"
        - "playoffs"
        - "competition"

    Any unknown input is lowercased and returned as-is.
    """
    if kind is None:
        return None

    k = kind.strip().lower()
    if not k:
        return None

    mapping = {
        "league": "league",
        "league competition": "league",
        "cup": "cup",
        "knockout cup": "cup",
        "tournament": "tournament",
        "championship": "championship",
        "season": "season",
        "playoffs": "playoffs",
        "play-off": "playoffs",
        "play-off phase": "playoffs",
        "competition": "competition",
    }

    return mapping.get(k, k)


# ---------------------------------------------------------------------------
# Frame definition
# ---------------------------------------------------------------------------


@dataclass
class CompetitionLeagueFrame:
    """
    Semantic frame for a sports competition / tournament / league.

    This frame is intended to support first-sentence descriptions such as:

        - "The Premier League is the top level of the English football
           league system."

        - "The UEFA Champions League is an annual club football competition
           organized by UEFA."

        - "The 2019–20 Premier League was the 28th season of the Premier League,
           the top English professional football league."

    Fields
    ------

    main_entity:
        The competition / league entity itself. This is the subject of
        the description (e.g. "Premier League", "UEFA Champions League").

    sport_lemma:
        Lemma for the sport (e.g. "football", "association football",
        "basketball", "ice hockey"). This is a *lemma*, not a surface string;
        the constructions layer will choose the appropriate NP.

    competition_kind:
        Coarse type of competition, normalized via `normalize_competition_kind`,
        e.g. "league", "cup", "tournament", "championship", "season",
        "playoffs". Can be None if unknown.

    level:
        Optional text describing the competitive level, e.g.:

            - "top tier"
            - "second division"
            - "regional league"

        This is a short semantic label that the rendering layer can
        incorporate into a predicate NP.

    organizing_body:
        Optional organizing body entity (e.g. "UEFA", "The Football Association").

    confederation:
        Optional confederation or higher-level governing body
        (e.g. "UEFA", "CONMEBOL").

    host_regions:
        List of locations (countries / regions) where the competition
        primarily takes place (e.g. [England], [England, Wales]).

    seasonal_scope:
        Optional time span representing the season or edition that this
        frame describes. For a timeless, generic competition article,
        this can be None. For season-specific frames (e.g. "2019–20
        Premier League") this can encode the season dates or years.

    founded:
        Optional time span representing when the competition was founded /
        established (e.g. start_year=1992). For a seasonal frame, this may
        be left None or used to refer to the underlying competition's origin.

    number_of_teams:
        Typical or current number of participating teams / clubs in the
        main phase (if known).

    participants:
        Optional list of participating entities (usually clubs, national
        teams, or franchises). This is mainly useful when generating
        enumeration sentences or detailed descriptions.

    promotion_to:
        Optional entity representing the higher competition to which
        teams can be promoted.

    relegation_to:
        Optional entity representing the lower competition to which
        teams can be relegated.

    format_summary:
        Short free-text summary of the competition format, in neutral
        lemma-ish English (e.g. "round-robin", "knock-out tournament",
        "group stage followed by knockout rounds"). The rendering layer
        can plug this into appropriate constructions.

    frequency:
        Optional label describing how often the competition occurs, e.g.:

            - "annual"
            - "biennial"
            - "quadrennial"

    champions:
        Optional list of current champions (one or more entities).
        For a seasonal frame, this would be the winners of that edition.

    most_successful_clubs:
        Optional list of historically most successful participants, e.g.
        those with the most titles.

    attributes:
        Arbitrary attribute map for additional neutral, language-agnostic
        properties, such as:

            {
                "age_group": "senior",
                "gender_category": "men",
                "professional_status": "professional",
                "domestic_or_international": "domestic",
            }

        This is intended for semantically meaningful predicates that the
        constructions layer may choose to surface or ignore.

    extra:
        Arbitrary metadata for downstream systems (IDs, raw JSON, etc.).
    """

    main_entity: Entity

    # Core identity
    sport_lemma: Optional[str] = None
    competition_kind: Optional[str] = None  # normalized in __post_init__
    level: Optional[str] = None

    # Governance and geography
    organizing_body: Optional[Entity] = None
    confederation: Optional[Entity] = None
    host_regions: List[Location] = field(default_factory=list)

    # Time and history
    seasonal_scope: Optional[TimeSpan] = None
    founded: Optional[TimeSpan] = None

    # Structure and participation
    number_of_teams: Optional[int] = None
    participants: List[Entity] = field(default_factory=list)
    promotion_to: Optional[Entity] = None
    relegation_to: Optional[Entity] = None
    format_summary: Optional[str] = None
    frequency: Optional[str] = None

    # Outcome-related info
    champions: List[Entity] = field(default_factory=list)
    most_successful_clubs: List[Entity] = field(default_factory=list)

    # Misc
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Initialization hooks
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # Normalize competition_kind once at creation time so that the
        # rest of the code can rely on a small, predictable inventory.
        if self.competition_kind is not None:
            self.competition_kind = normalize_competition_kind(self.competition_kind)

        # Defensively ensure lists and dicts are real lists/dicts even if
        # someone passed tuples or other iterables.
        self.host_regions = list(self.host_regions)
        self.participants = list(self.participants)
        self.champions = list(self.champions)
        self.most_successful_clubs = list(self.most_successful_clubs)
        self.attributes = dict(self.attributes)
        self.extra = dict(self.extra)

    # ------------------------------------------------------------------
    # (Optional) dict helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_entity(value: Any) -> Optional[Entity]:
        """
        Helper to coerce loose input into an Entity, if possible.

        This is intentionally conservative. It supports:

            - already-an-Entity instances
            - minimal dicts {"name": "..."} or {"id": "...", "name": "..."}

        More complex normalization (e.g. via Wikidata or an external index)
        should live in semantics.aw_bridge or higher-level ETL code.
        """
        if value is None:
            return None

        if isinstance(value, Entity):
            return value

        if isinstance(value, dict):
            # Minimal best-effort normalization
            name = value.get("name") or value.get("label") or ""
            entity_id = value.get("id")
            entity_type = value.get("entity_type")
            gender = value.get("gender", "unknown")
            human = bool(value.get("human", False))
            lemmas = list(value.get("lemmas", []))
            features = dict(value.get("features", {}))
            extra = dict(value.get("extra", {}))
            return Entity(
                id=entity_id,
                name=name,
                gender=gender,
                human=human,
                entity_type=entity_type,
                lemmas=lemmas,
                features=features,
                extra=extra,
            )

        # Last resort: treat as opaque name
        return Entity(name=str(value))

    @staticmethod
    def _coerce_location(value: Any) -> Optional[Location]:
        """
        Helper to coerce loose input into a Location, if possible.

        Supports:
            - existing Location instances
            - minimal dicts {"name": "..."} or {"id": "...", "name": "..."}
        """
        if value is None:
            return None

        if isinstance(value, Location):
            return value

        if isinstance(value, dict):
            name = value.get("name") or value.get("label") or ""
            loc_id = value.get("id")
            kind = value.get("kind")
            country_code = value.get("country_code")
            features = dict(value.get("features", {}))
            extra = dict(value.get("extra", {}))
            return Location(
                id=loc_id,
                name=name,
                kind=kind,
                country_code=country_code,
                features=features,
                extra=extra,
            )

        return Location(name=str(value))

    @staticmethod
    def _coerce_timespan(value: Any) -> Optional[TimeSpan]:
        """
        Helper to coerce loose input into a TimeSpan, if possible.

        Supports:
            - existing TimeSpan instances
            - dicts with a subset of TimeSpan fields
        """
        if value is None:
            return None

        if isinstance(value, TimeSpan):
            return value

        if isinstance(value, dict):
            return TimeSpan(
                start_year=value.get("start_year"),
                end_year=value.get("end_year"),
                start_month=value.get("start_month"),
                start_day=value.get("start_day"),
                end_month=value.get("end_month"),
                end_day=value.get("end_day"),
                approximate=bool(value.get("approximate", False)),
                extra=dict(value.get("extra", {})),
            )

        # Unsupported format → ignore, but do not crash
        return None

    @classmethod
    def from_loose_dict(cls, data: Dict[str, Any]) -> "CompetitionLeagueFrame":
        """
        Build a CompetitionLeagueFrame from a loose dictionary.

        This is a convenience layer for callers that have AW-style or
        Wikidata-style JSON. It performs *minimal* normalization and
        defers heavier ETL to dedicated bridge modules.

        Expected keys (all optional except main_entity):

            - main_entity: dict | Entity | str
            - sport_lemma: str
            - competition_kind: str
            - level: str
            - organizing_body: dict | Entity | str
            - confederation: dict | Entity | str
            - host_regions: list[dict|Location|str]
            - seasonal_scope: dict | TimeSpan
            - founded: dict | TimeSpan
            - number_of_teams: int
            - participants: list[dict|Entity|str]
            - promotion_to: dict | Entity | str
            - relegation_to: dict | Entity | str
            - format_summary: str
            - frequency: str
            - champions: list[dict|Entity|str]
            - most_successful_clubs: list[dict|Entity|str]
            - attributes: dict
            - extra: dict
        """
        if "main_entity" not in data:
            raise ValueError(
                "CompetitionLeagueFrame.from_loose_dict requires 'main_entity'"
            )

        main_entity = cls._coerce_entity(data["main_entity"])
        if main_entity is None:
            raise ValueError("Could not normalize 'main_entity' into Entity")

        organizing_body = cls._coerce_entity(data.get("organizing_body"))
        confederation = cls._coerce_entity(data.get("confederation"))
        promotion_to = cls._coerce_entity(data.get("promotion_to"))
        relegation_to = cls._coerce_entity(data.get("relegation_to"))

        host_regions_raw = data.get("host_regions") or []
        host_regions = [
            loc
            for loc in (cls._coerce_location(v) for v in host_regions_raw)
            if loc is not None
        ]

        participants_raw = data.get("participants") or []
        participants = [
            ent
            for ent in (cls._coerce_entity(v) for v in participants_raw)
            if ent is not None
        ]

        champions_raw = data.get("champions") or []
        champions = [
            ent
            for ent in (cls._coerce_entity(v) for v in champions_raw)
            if ent is not None
        ]

        msc_raw = data.get("most_successful_clubs") or []
        most_successful_clubs = [
            ent for ent in (cls._coerce_entity(v) for v in msc_raw) if ent is not None
        ]

        seasonal_scope = cls._coerce_timespan(data.get("seasonal_scope"))
        founded = cls._coerce_timespan(data.get("founded"))

        return cls(
            main_entity=main_entity,
            sport_lemma=data.get("sport_lemma"),
            competition_kind=data.get("competition_kind"),
            level=data.get("level"),
            organizing_body=organizing_body,
            confederation=confederation,
            host_regions=host_regions,
            seasonal_scope=seasonal_scope,
            founded=founded,
            number_of_teams=data.get("number_of_teams"),
            participants=participants,
            promotion_to=promotion_to,
            relegation_to=relegation_to,
            format_summary=data.get("format_summary"),
            frequency=data.get("frequency"),
            champions=champions,
            most_successful_clubs=most_successful_clubs,
            attributes=dict(data.get("attributes", {})),
            extra=dict(data.get("extra", {})),
        )

    def to_minimal_dict(self) -> Dict[str, Any]:
        """
        Return a minimal JSON-serializable representation of this frame.

        This is intentionally lossy and focused on fields that a frontend
        or debugging UI is most likely to care about. Structured objects
        (Entity, Location, TimeSpan) are represented by their most salient
        identifiers (ID / name / year).

        The exact shape is not considered stable API for external callers;
        adapt as needed.
        """

        def _entity_repr(entity: Optional[Entity]) -> Optional[Dict[str, Any]]:
            if entity is None:
                return None
            return {
                "id": entity.id,
                "name": entity.name,
                "entity_type": entity.entity_type,
            }

        def _location_repr(location: Optional[Location]) -> Optional[Dict[str, Any]]:
            if location is None:
                return None
            return {
                "id": location.id,
                "name": location.name,
                "kind": location.kind,
                "country_code": location.country_code,
            }

        def _timespan_repr(timespan: Optional[TimeSpan]) -> Optional[Dict[str, Any]]:
            if timespan is None:
                return None
            return {
                "start_year": timespan.start_year,
                "end_year": timespan.end_year,
                "start_month": timespan.start_month,
                "start_day": timespan.start_day,
                "end_month": timespan.end_month,
                "end_day": timespan.end_day,
                "approximate": timespan.approximate,
            }

        return {
            "frame_type": "competition_league",
            "main_entity": _entity_repr(self.main_entity),
            "sport_lemma": self.sport_lemma,
            "competition_kind": self.competition_kind,
            "level": self.level,
            "organizing_body": _entity_repr(self.organizing_body),
            "confederation": _entity_repr(self.confederation),
            "host_regions": [_location_repr(loc) for loc in self.host_regions],
            "seasonal_scope": _timespan_repr(self.seasonal_scope),
            "founded": _timespan_repr(self.founded),
            "number_of_teams": self.number_of_teams,
            "participants": [_entity_repr(ent) for ent in self.participants],
            "promotion_to": _entity_repr(self.promotion_to),
            "relegation_to": _entity_repr(self.relegation_to),
            "format_summary": self.format_summary,
            "frequency": self.frequency,
            "champions": [_entity_repr(ent) for ent in self.champions],
            "most_successful_clubs": [
                _entity_repr(ent) for ent in self.most_successful_clubs
            ],
            "attributes": dict(self.attributes),
            "extra": dict(self.extra),
        }


__all__ = [
    "CompetitionLeagueFrame",
    "normalize_competition_kind",
]
