# semantics\meta\article_document_frame.py
"""
semantics/meta/article_document_frame.py
---------------------------------------

Top-level meta frame representing a whole article or document.

This frame acts as a container for:

- The main subject entity (if any).
- Basic page metadata (title, language, project, ids).
- An ordered list of section summaries.
- A collection of source / citation descriptors.

It is intended as the primary input for document-level NLG routines:
discourse planning, section ordering, and global realization. The
concrete section and source frames are defined in:

- semantics.meta.section_summary_frame.SectionSummaryFrame
- semantics.meta.source_citation_frame.SourceCitationFrame
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity  # core semantic unit
from semantics.meta.section_summary_frame import SectionSummaryFrame
from semantics.meta.source_citation_frame import SourceCitationFrame


@dataclass
class ArticleDocumentFrame:
    """
    Top-level meta frame representing a whole article or document.

    Fields
    ------

    frame_type:
        Stable label identifying this as an article-level meta frame.
        For compatibility with the common `Frame` protocol, this is
        fixed to "article".

    subject:
        Optional main subject entity for the article, if there is a
        single clear topic (e.g. a person, city, organization). For
        articles that do not have a single primary subject (such as
        list pages or some disambiguation pages), this may be `None`.

    title:
        Canonical article title in the target project, for example the
        page title on Wikipedia.

    language:
        Optional language code (ISO 639-1 or project-convention), such
        as "en", "fr", "sw". If omitted, callers are expected to track
        language separately.

    project:
        Optional project identifier, for example "wikipedia",
        "wikivoyage", or a downstream consumer-specific project label.

    page_id:
        Optional page identifier in the source system (e.g. MediaWiki
        page id), if available.

    revision_id:
        Optional revision identifier in the source system, if available.

    sections:
        Ordered list of section-level frames summarizing the content of
        the article. Each entry is a `SectionSummaryFrame`, typically
        representing sections such as "Early life", "Career", "Legacy",
        etc.

    sources:
        List of `SourceCitationFrame` objects describing sources used in
        this article. This list is primarily intended for iterating over
        all sources when building reference lists or debugging.

    source_index:
        Mapping from source keys / identifiers (for example citation
        ids) to `SourceCitationFrame` objects, to allow efficient lookup
        when resolving inline citation references.

    extra:
        Arbitrary metadata bag for anything else that should travel
        along with the article document frame but does not have a
        dedicated field. Values should be JSON-serializable; typical
        uses include provenance, pipeline debug information, or raw
        source snippets.
    """

    # Common frame protocol discriminator
    frame_type: str = "article"

    # Core subject (optional)
    subject: Optional[Entity] = None

    # Page-level metadata
    title: Optional[str] = None  # canonical article title
    language: Optional[str] = None  # ISO 639-1 (e.g. "en", "fr")
    project: Optional[str] = None  # e.g. "wikipedia", "wikivoyage"
    page_id: Optional[str] = None
    revision_id: Optional[str] = None

    # Structure
    sections: List[SectionSummaryFrame] = field(default_factory=list)

    # Sources
    sources: List[SourceCitationFrame] = field(default_factory=list)
    source_index: Dict[str, SourceCitationFrame] = field(default_factory=dict)

    # Arbitrary metadata
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["ArticleDocumentFrame"]
