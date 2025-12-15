# semantics\entity\software_protocol_standard_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity, Location, TimeSpan


@dataclass
class SoftwareProtocolStandardFrame:
    """
    High-level semantic frame for software, websites, protocols, and technical standards.

    This frame family is intended for Wikipedia-style lead sentences and short
    summaries such as:

        - "Firefox is a free and open-source web browser developed by Mozilla."
        - "HTML is the standard markup language for documents designed to be displayed in a web browser."
        - "TLS is a cryptographic protocol designed to provide communications security over a computer network."
        - "RFC 2616 is an IETF standard that defines HTTP/1.1."

    The goal is to capture enough structure for cross-linguistic realizations,
    while keeping the representation compact and implementation-oriented.

    Core design principles:
        - Lemmas, not surface forms: fields that correspond to lexical choices
          (e.g. "web browser", "cryptographic protocol") are stored as plain
          lemma strings. Language-specific morphology and syntax are handled
          elsewhere.
        - Entities for participants: organizations, people, and related
          technologies are represented as `Entity` instances.
        - Coarse but extensible time representation: important dates use
          `TimeSpan` rather than raw strings.
        - Open-ended "attributes" / "extra" for data that does not yet have a
          dedicated field.

    Fields
    ------

    frame_type:
        Stable identifier for this frame family. Always
        "software_protocol_standard". Included to satisfy the generic
        `Frame` protocol used by the NLG layer.

    main_entity:
        The software product, website, protocol, or standard this frame is
        about. Typically corresponds to a Wikidata item such as "Firefox",
        "HTML", "TLS", "RFC 2616", etc.

    product_kind:
        Coarse classification hint for `main_entity`. Common values include
        (but are not limited to):

            - "software"
            - "website"
            - "web_service"
            - "protocol"
            - "standard"
            - "specification"
            - "file_format"
            - "markup_language"
            - "programming_language"

        The inventory is intentionally open; upstream code can normalize or
        constrain it if needed.

    category_lemmas:
        Lemmas describing the primary functional category of the subject, e.g.:

            ["web browser"]
            ["operating system"]
            ["cryptographic protocol"]
            ["markup language"]
            ["file transfer protocol"]

        These are typically realized as predicate nominals ("X is a Y").

    descriptor_lemmas:
        Lemmas for adjectival or compound descriptors that modify the category,
        e.g.:

            ["free", "open-source"]
            ["proprietary"]
            ["cross-platform"]
            ["client-server"]

        These are realized as modifiers of the category (e.g. "a free and
        open-source web browser").

    developers:
        List of entities that originally developed the software / protocol /
        standard. Often organizations, but may include individual people.

            [Entity(name="Mozilla"), Entity(name="Mozilla Foundation")]

    maintainers:
        List of entities currently maintaining or stewarding the project, if
        different from the original developers.

            [Entity(name="Mozilla Corporation")]

    standards_bodies:
        For protocols/standards, entities representing formal bodies or working
        groups, e.g.:

            [Entity(name="IETF"), Entity(name="W3C"), Entity(name="ISO")]

        Empty for purely de facto software projects without a standards body.

    origin_location:
        Optional location associated with the origin of the software/standard
        (e.g. headquarters of the main developer, country where the standard
        was first adopted). This is deliberately coarse and optional.

    initial_release:
        Time span for the initial release or adoption. Typically only
        `start_year` is filled (e.g. 1994), but more precise dates may be
        provided.

    latest_release:
        Time span for the latest notable release or revision (e.g. latest
        version of the software, latest published edition of the standard).

    current_version:
        String label for the best-known current version or edition, e.g.:

            "1.0"
            "3.6"
            "HTTP/1.1"
            "HTML5"
            "TLS 1.3"

        This is intentionally not parsed; construction code can choose whether
        to mention it.

    current_version_time:
        Time span corresponding to `current_version` (e.g. year or date when
        that version was released or standardized).

    target_platform_entities:
        Entities representing operating systems, hardware platforms, or runtime
        environments the software targets, e.g.:

            [Entity(name="Windows"), Entity(name="macOS"), Entity(name="Linux")]

    target_platform_tags:
        Free-form platform descriptors that do not warrant or lack an `Entity`,
        e.g.:

            ["web", "mobile", "desktop", "server"]

        May co-exist with `target_platform_entities`.

    license_lemmas:
        Lemmas describing licensing, e.g.:

            ["free software"]
            ["proprietary software"]
            ["MIT License"]
            ["GPL"]

        These can be realized as part of the predicate (e.g. "a free and
        open-source web browser") or in follow-up sentences.

    programming_language_lemmas:
        Lemmas for implementation languages, e.g.:

            ["C++"]
            ["JavaScript"]
            ["Rust"]

        Typically realized in sentences such as
        "X is written in Y and Z."

    protocol_layers:
        For network protocols / standards, textual labels for their layer or
        placement in a stack, e.g.:

            ["application layer"]
            ["transport layer"]
            ["link layer"]

        These can be realized as "an application-layer protocol", etc.

    domains:
        High-level domains or application areas the technology belongs to, e.g.:

            ["web"]
            ["cryptography"]
            ["networking"]
            ["audio compression"]
            ["markup"]

        Useful for optional additional context ("in web development", "in
        computer networking", ...).

    status:
        Coarse lifecycle / activity status, e.g.:

            "active"
            "discontinued"
            "historical"
            "experimental"
            "deprecated"

        As with other label fields, the inventory is open.

    open_standard:
        Optional flag indicating whether the protocol/standard is generally
        considered an open standard (True), clearly not open (False), or
        unspecified (None).

    website_url:
        Canonical project or documentation URL, e.g. a homepage or spec URL.
        This is metadata; the NLG layer may or may not surface it.

    related_entities:
        Mapping from relation label → list of related entities, for example:

            {
                "implements": [Entity(name="HTTP")],
                "extends": [Entity(name="SGML")],
                "successor": [Entity(name="HTTP/2")],
                "predecessor": [Entity(name="SSL")],
            }

        Relation labels are free-form strings; callers can choose their own
        inventory.

    attributes:
        Arbitrary attribute map keyed by short labels, e.g.:

            {
                "use_cases": ["web browsing", "email"],
                "notable_features": ["tabbed browsing", "extensions"],
            }

        This is intended for small structured facts that do not justify a
        dedicated field but are still useful for generation.

    extra:
        Arbitrary metadata bag (e.g. original JSON from Wikidata/AW, IDs,
        provenance flags). Not interpreted by the core NLG system.

    Notes
    -----
    - This frame is designed to be generic enough to cover software projects,
      websites, protocols, and technical standards with one schema.
    - Downstream code can specialize behavior based on `product_kind`,
      `category_lemmas`, or other fields.
    """

    #: Stable identifier for this frame family (used by generic Frame protocols).
    frame_type: str = field(init=False, default="software_protocol_standard")

    # Core subject -----------------------------------------------------------
    main_entity: Entity

    # High-level classification ---------------------------------------------
    product_kind: str = "software"
    category_lemmas: List[str] = field(default_factory=list)
    descriptor_lemmas: List[str] = field(default_factory=list)

    # Actors / organizations -------------------------------------------------
    developers: List[Entity] = field(default_factory=list)
    maintainers: List[Entity] = field(default_factory=list)
    standards_bodies: List[Entity] = field(default_factory=list)

    # Origin and timeline ----------------------------------------------------
    origin_location: Optional[Location] = None
    initial_release: Optional[TimeSpan] = None
    latest_release: Optional[TimeSpan] = None
    current_version: Optional[str] = None
    current_version_time: Optional[TimeSpan] = None

    # Platforms and technical environment -----------------------------------
    target_platform_entities: List[Entity] = field(default_factory=list)
    target_platform_tags: List[str] = field(default_factory=list)
    license_lemmas: List[str] = field(default_factory=list)
    programming_language_lemmas: List[str] = field(default_factory=list)
    protocol_layers: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)

    # Status and metadata ----------------------------------------------------
    status: Optional[str] = None
    open_standard: Optional[bool] = None
    website_url: Optional[str] = None

    # Rich relations / attributes -------------------------------------------
    related_entities: Dict[str, List[Entity]] = field(default_factory=dict)
    attributes: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SoftwareProtocolStandardFrame"]
