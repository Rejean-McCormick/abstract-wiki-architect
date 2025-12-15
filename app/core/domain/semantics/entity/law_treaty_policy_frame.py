# semantics\entity\law_treaty_policy_frame.py
# semantics/entity/law_treaty_policy_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Event


def normalize_instrument_kind(kind: Optional[str]) -> Optional[str]:
    """
    Normalize a loose legal-instrument kind string into a small canonical set.

    Canonical values (extend as needed):

        - "treaty"
        - "law"
        - "constitution"
        - "policy"
        - "agreement"
        - "convention"
        - "charter"
        - "statute"

    Any unknown non-empty input is lowercased and returned as-is.
    """
    if kind is None:
        return None

    k = kind.strip().lower()
    if not k:
        return None

    mapping = {
        "treaty": "treaty",
        "international treaty": "treaty",
        "agreement": "agreement",
        "international agreement": "agreement",
        "convention": "convention",
        "law": "law",
        "act": "law",
        "statute": "statute",
        "policy": "policy",
        "public policy": "policy",
        "constitution": "constitution",
        "constitutional document": "constitution",
        "charter": "charter",
    }

    return mapping.get(k, k)


@dataclass
class LawTreatyPolicyFrame:
    """
    Semantic frame for laws, treaties, policies, constitutions, and similar
    legal instruments.

    This frame is designed for first-sentence / short-intro descriptions of
    entities such as:

        - international treaties and conventions,
        - national statutes and acts,
        - constitutions and charters,
        - major public policies.

    It is language-neutral: no inflected text or localized phrasing is stored
    here. The NLG layer consumes this frame and chooses appropriate
    constructions to realize it in different languages.

    Fields
    ------

    frame_type:
        Canonical frame-type string for routing and inspection.
        For this frame it is always "entity.legal_instrument".

    main_entity:
        The legal instrument entity itself (the article subject), e.g.
        "Treaty of Lisbon", "United States Constitution", "Affordable Care Act".

    instrument_kind:
        Coarse type of the instrument, normalized via `normalize_instrument_kind`,
        e.g. "treaty", "law", "constitution", "policy". Can be None if unknown.

    jurisdiction:
        Jurisdiction or primary legal system the instrument belongs to,
        typically a country, supranational union, or international body.

    signing_event:
        Event describing the signing or adoption of the instrument,
        if applicable. For multi-stage instruments, this typically refers
        to the formal signing ceremony or adoption date.

    coming_into_force_event:
        Event describing when the instrument entered into force (came into
        effect). May be distinct from the signing date.

    repeal_event:
        Event describing repeal, replacement, or abrogation, when relevant.

    status:
        Short label for the current legal status, e.g.:

            - "in force"
            - "repealed"
            - "partially in force"
            - "superseded"

    parties:
        For treaties / agreements: parties or signatories (states, organizations).
        For domestic laws, this is usually empty.

    subjects:
        High-level subject domains or policy areas, as simple lemmas, e.g.:

            - "environmental protection"
            - "trade"
            - "civil rights"

    articles_or_sections:
        Identifiers of key articles / sections (e.g. "Article 1", "Section 2"),
        primarily for reference and not typically surfaced in the lead sentence.

    legal_citations:
        Legal citation strings, such as official publication references,
        docket numbers, or standard citation formats (e.g. "Pub. L. 111–148").

    attributes:
        Arbitrary attribute map for additional structured properties, such as:

            {
                "scope": "international",
                "binding": True,
                "subject_matter": ["trade", "intellectual property"],
                "language_versions": ["english", "french"],
            }

        The NLG layer may choose to surface some of these in extended
        descriptions; unknown keys are safely ignored.

    extra:
        Opaque metadata for downstream systems: raw JSON fragments, source IDs,
        etc. This is never interpreted by the NLG layer but preserved for
        traceability.
    """

    frame_type: str = "entity.legal_instrument"

    # Core identity
    main_entity: Entity = field(default_factory=Entity)
    instrument_kind: Optional[str] = None

    # Jurisdiction and temporal lifecycle
    jurisdiction: Optional[Entity] = None
    signing_event: Optional[Event] = None
    coming_into_force_event: Optional[Event] = None
    repeal_event: Optional[Event] = None
    status: Optional[str] = None

    # Parties and subject matter
    parties: List[Entity] = field(default_factory=list)
    subjects: List[str] = field(default_factory=list)
    articles_or_sections: List[str] = field(default_factory=list)
    legal_citations: List[str] = field(default_factory=list)

    # Misc
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Normalize kind once at creation time so other code can rely on
        # a small, predictable inventory.
        if self.instrument_kind is not None:
            self.instrument_kind = normalize_instrument_kind(self.instrument_kind)

        # Defensive copying and type normalization for containers.
        self.parties = list(self.parties)
        self.subjects = list(self.subjects)
        self.articles_or_sections = list(self.articles_or_sections)
        self.legal_citations = list(self.legal_citations)
        self.attributes = dict(self.attributes)
        self.extra = dict(self.extra)


__all__ = ["LawTreatyPolicyFrame", "normalize_instrument_kind"]
