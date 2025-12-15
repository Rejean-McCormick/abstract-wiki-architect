# semantics\meta\section_summary_frame.py
# semantics/meta/section_summary_frame.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import TimeSpan, SemanticFrame


@dataclass
class SectionSummaryFrame:
    """
    Meta frame representing one logical section within an article or document.

    This is a content-packaging frame:

    - It groups one or more underlying semantic frames (biographical, event,
      relational, narrative, etc.) that should be realized in this section.
    - It carries section-level metadata such as heading text, hierarchy level,
      and an optional time span describing the scope of the section.
    - It is intended to be used by higher-level planners and renderers that
      walk an article structure (e.g. ArticleDocumentFrame.sections) and call
      the NLG frontend for each contained content frame.

    Fields
    ------

    frame_type:
        Stable discriminator for routing and introspection. Always "section".

    section_id:
        Logical identifier for the section, typically language-neutral codes
        such as "lead", "early_life", "career", "works", "legacy". This can
        also be a slug derived from a heading.

    heading:
        Human-readable heading text for this section in the working language,
        if known (e.g. "Early life", "Career"). Optional; some callers may
        infer headings from section_id.

    level:
        Hierarchical level of the section. Conventionally:
            1 = top-level (e.g. page title / lead)
            2 = h2
            3 = h3
        and so on. The exact mapping to markup is up to the caller.

    parent_section_id:
        Optional identifier of a parent section for nested structures.
        If None, this section is considered top-level (within the article).

    subject_time_span:
        Optional TimeSpan describing the temporal scope of the section
        content, such as the years covered by a "Career" section.

    topic_span_description:
        Optional free-text or language-neutral descriptor of the scope,
        e.g. "childhood", "World War II period", "post-1990 reforms".

    frames:
        Ordered list of underlying semantic frames to be realized in this
        section. These are typically BioFrame, Event, or other higher-level
        frames. The SemanticFrame alias currently resolves to BioFrame but
        is intended to expand to a union of supported frame types.

    ordering_hint:
        Optional string hint for ordering / rendering logic (e.g.
        "chronological", "by_importance"). Interpretation is left to the
        planner / renderer.

    max_frames:
        Optional soft cap on how many frames from `frames` should actually
        be realized when generating text. This can be used by planners to
        truncate very dense sections.

    extra:
        Arbitrary metadata for caller-specific needs (provenance, UI hints,
        original section ids, etc.). Not interpreted by core semantics.
    """

    frame_type: str = "section"

    # Identity / hierarchy
    section_id: Optional[str] = None
    heading: Optional[str] = None
    level: int = 2
    parent_section_id: Optional[str] = None

    # Scope
    subject_time_span: Optional[TimeSpan] = None
    topic_span_description: Optional[str] = None

    # Content frames to be realized in this section
    frames: List[SemanticFrame] = field(default_factory=list)

    # Optional hints for ordering/rendering of frames
    ordering_hint: Optional[str] = None
    max_frames: Optional[int] = None

    # Arbitrary metadata
    extra: Dict[str, Any] = field(default_factory=dict)


__all__ = ["SectionSummaryFrame"]
