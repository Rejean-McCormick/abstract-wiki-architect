# app\core\domain\semantics\meta\source_citation_frame.py
# semantics\meta\source_citation_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional


@dataclass
class SourceCitationFrame:
    """
    Meta frame representing a single bibliographic or web source and its
    relationship to frames / statements in the article-level semantics.
    """

    #: Canonical frame type label used in routing / serialization.
    frame_type: ClassVar[str] = "source"

    # --- Stable identity -----------------------------------------------------

    # e.g. "S1", "REF-001", DOI, or Wikidata QID. Intended to be stable within
    # the project so that other structures can point back to this source.
    source_id: str

    # --- Bibliographic metadata (all optional) -------------------------------

    # Human-facing title of the source (article title, book title, page title).
    title: Optional[str] = None

    # List of author / creator names, in order.
    authors: List[str] = field(default_factory=list)

    # Year of publication / release, if known.
    year: Optional[int] = None

    # Journal, newspaper, website, or other container name.
    publication: Optional[str] = None

    # Publisher or publishing organization (may differ from `publication`).
    publisher: Optional[str] = None

    # Edition information for books or similar works.
    edition: Optional[str] = None

    # Volume / issue identifiers for periodicals.
    volume: Optional[str] = None
    issue: Optional[str] = None

    # Page range or article number (as free text, e.g. "12–34" or "e1234").
    pages: Optional[str] = None

    # --- Access / identification --------------------------------------------

    # Direct URL to the resource, if available.
    url: Optional[str] = None

    # Digital Object Identifier.
    doi: Optional[str] = None

    # International Standard Book Number.
    isbn: Optional[str] = None

    # Date when the source was accessed, in ISO format ("YYYY-MM-DD").
    access_date_iso: Optional[str] = None

    # --- Type / classification ----------------------------------------------

    # Broad source category, e.g. "web", "book", "article", "dataset".
    source_type: Optional[str] = None

    # Language of the source, ISO 639-1 code where possible.
    language: Optional[str] = None

    # --- Provenance links ----------------------------------------------------

    # IDs of frames (events, entities, etc.) that this source supports.
    supports_frames: List[str] = field(default_factory=list)

    # IDs of fine-grained statements that this source supports.
    supports_statements: List[str] = field(default_factory=list)

    # IDs of fine-grained statements that this source contradicts.
    contradicts_statements: List[str] = field(default_factory=list)

    # --- Arbitrary metadata --------------------------------------------------

    # Free-form metadata for project-specific extensions (e.g. ranking, tags).
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SourceCitationFrame"]
