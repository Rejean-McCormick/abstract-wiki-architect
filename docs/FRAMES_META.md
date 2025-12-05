
# Meta frames

This document specifies the “meta” frame families used for wrapping lower-level semantic frames into full articles, sections, and citation bundles.

Meta frames are *not* directly about real-world entities or events. Instead, they model:

* an article as a whole,
* sections within that article, and
* the sources and provenance that support the content.

They sit on top of the ordinary semantic frames (biographies, events, relational facts, timelines, etc.) that are defined in `semantics.types` and friends.

---

## 1. Relationship to other layers

The system already distinguishes:

* **Semantic frames** (e.g. `BioFrame`, `Event`/`EventFrame`) under `semantics.types`.
* **Frontend API** (`generate`, `generate_bio`, `NLGSession`) under `nlg.api`.
* **Discourse & planning** (`discourse/planner.py`, `discourse/state.py`) for multi-sentence grouping.

Meta frames sit *above* these:

* They bundle one or more “content frames” into a document/section structure.
* They carry **layout** and **status** metadata (which sections exist, their order, heading labels).
* They attach **citation bundles** used for attribution and QA.

The meta layer does **not** alter the semantics of the underlying frames; it only packages them and adds provenance.

---

## 2. Meta frame families

This document standardizes three meta frame families:

1. **Article / document frame**  
   Top-level representation of a whole article or document in terms of:
   * subject entity (e.g. `Entity` for “Marie Curie”),
   * list of section frames,
   * article-level metadata (language, wiki project, revision id).

2. **Section summary frame**  
   Representation of an article section (e.g. “Early life”, “Career”), defined by:
   * section type and heading,
   * time span or scope,
   * list of semantic frames to be realized in this section.

3. **Source / citation frame**  
   Cross-language representation of sources (e.g. references, web pages, books):
   * source metadata (title, authors, year, URL),
   * how the source is cited,
   * which frames / statements are supported.

At the JSON / catalogue level, these correspond to the canonical `frame_type` strings in the meta family:

* `meta.article` – article / document frame
* `meta.section_summary` – section summary frame
* `meta.source` – source / citation frame

These are the three members of the `"meta"` entry in `FRAME_FAMILIES` and related QA tests. :contentReference[oaicite:0]{index=0}

These families are designed to be **language-neutral** and **layout-neutral**: rendering them to concrete wiki markup or reference lists is the responsibility of specific renderers or caller code.

---

## 3. Article / document frame

### 3.1 Purpose

`ArticleDocumentFrame` is the top-level container for everything the renderer knows about a given article:

* what the **main subject** is (usually an `Entity` or `BioFrame.main_entity`),
* which **sections** are present and in what order,
* which **sources** are known,
* minimal article metadata (wiki, language, page id, revision id).

The same semantic frames (bio, event, relational, narrative) can appear in multiple sections across different wikis or language editions; `ArticleDocumentFrame` does not assume that section boundaries are uniquely determined by semantics.

### 3.2 Suggested Python shape

The exact data classes live in `semantics.types` / `semantics.meta` and should be treated as the source of truth, but a typical shape looks like:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from semantics.types import Entity  # core semantic unit
from nlg.semantics import Frame     # protocol base: has a frame_type attribute


@dataclass
class ArticleDocumentFrame:
    """
    Top-level meta frame representing a whole article or document.
    """

    # Canonical discriminator for the meta article family
    frame_type: str = "meta.article"

    # Identity / subject
    subject: Optional[Entity] = None
    title: Optional[str] = None          # canonical article title
    language: Optional[str] = None       # ISO 639-1 (e.g. "en", "fr")
    project: Optional[str] = None        # e.g. "wikipedia", "wikivoyage"
    page_id: Optional[str] = None
    revision_id: Optional[str] = None

    # Structure
    sections: List["SectionSummaryFrame"] = field(default_factory=list)

    # Sources
    sources: List["SourceCitationFrame"] = field(default_factory=list)
    source_index: Dict[str, "SourceCitationFrame"] = field(default_factory=dict)

    # Arbitrary metadata
    extra: Dict[str, Any] = field(default_factory=dict)
````

Notes:

* `frame_type="meta.article"` makes this compatible with the common `Frame` protocol and the meta frame catalogue.
* `subject` is optional: some documents (lists, disambiguation pages) may not have a single main entity.
* `sections` is ordered; each entry is a `SectionSummaryFrame`.
* `sources` and `source_index` provide both a list and an id-indexed map for efficient lookup by citation keys.

### 3.3 Lifecycle

A typical lifecycle for `ArticleDocumentFrame`:

1. **Normalization**
   An upstream “AW bridge” or reader builds `Entity`, `BioFrame`, `Event`, and other semantic frames from raw JSON.
2. **Structuring**
   A page-level normalizer groups those frames into section-level bundles and wraps everything into a single `ArticleDocumentFrame`.
3. **Rendering**
   The frontend walks `article.sections` and calls `generate(lang, frame)` for each content frame.
4. **Post-processing**
   A wiki-specific layer (outside this repo) adds headings, reference lists, templates, and any non-linguistic markup.

Meta frames deliberately avoid making commitments about wiki templates, citation styles, or section naming schemes beyond a small set of conventional codes.

---

## 4. Section summary frame

### 4.1 Purpose

`SectionSummaryFrame` describes a logical section in an article (or a sub-section, if nested):

* “Lead” / “Intro”
* “Early life”
* “Career”
* “Works”
* “Legacy”
* “References” (if you want to model that as content)

It is a **content packaging** frame:

* It holds a list of underlying semantic frames (events, timelines, relational facts).
* It allows higher-level code to decide which frames go into which section for rendering.
* It carries section-level metadata (heading text, type code, scope/time span).

### 4.2 Suggested Python shape

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from nlg.semantics import Frame
from semantics.types import TimeSpan


@dataclass
class SectionSummaryFrame:
    """
    Meta frame representing one section within an article.
    """

    # Canonical discriminator for the section-summary meta family
    frame_type: str = "meta.section_summary"

    # Identity / hierarchy
    section_id: Optional[str] = None      # e.g. "lead", "early_life", "career"
    heading: Optional[str] = None         # localized heading text, if known
    level: int = 2                        # 1 = top-level, 2 = h2, etc.
    parent_section_id: Optional[str] = None

    # Scope
    subject_time_span: Optional[TimeSpan] = None
    topic_span_description: Optional[str] = None  # free-text, language-neutral

    # Content frames to be realized in this section
    frames: List[Frame] = field(default_factory=list)

    # Optional hints for ordering/rendering of frames
    ordering_hint: Optional[str] = None   # e.g. "chronological", "by_importance"
    max_frames: Optional[int] = None      # optional cap for summarization

    # Arbitrary metadata
    extra: Dict[str, Any] = field(default_factory=dict)
```

Notes:

* `section_id` is a stable internal code; `heading` may be localized later.
* `frames` is a heterogeneous list: any object implementing `Frame` is allowed (`BioFrame`, `Event`, relational frames, timelines, etc.).
* `subject_time_span` and `topic_span_description` are optional hints; engines may ignore them or use them to select tenses and aspect.

### 4.3 Section types

Implementations should agree on a small, extensible vocabulary of `section_id` codes, for example:

* `lead`
* `short_description`
* `infobox`
* `early_life`
* `education`
* `career`
* `works`
* `awards`
* `legacy`
* `personal_life`
* `references`

The exact set is not enforced by the core library; they are conventions used by upstream normalizers and downstream renderers.

---

## 5. Source / citation frame

### 5.1 Purpose

`SourceCitationFrame` captures **provenance** for facts and frames:

* where a fact came from (web page, book, dataset),
* how it should be cited,
* which parts of the article rely on it.

It is deliberately independent of any particular citation style (e.g. APA, Chicago, wiki templates). Those styles are applied *outside* this layer.

### 5.2 Suggested Python shape

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SourceCitationFrame:
    """
    Meta frame representing a single source/citation.
    """

    # Canonical discriminator for the source meta family
    frame_type: str = "meta.source"

    # Stable identity
    source_id: str                         # e.g. "S1", "REF-001", DOI, or QID

    # Bibliographic metadata (optional but recommended)
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    publication: Optional[str] = None      # journal, newspaper, site, publisher
    publisher: Optional[str] = None
    edition: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None

    # Access / identification
    url: Optional[str] = None
    doi: Optional[str] = None
    isbn: Optional[str] = None
    access_date_iso: Optional[str] = None  # e.g. "2024-05-01"

    # Type / classification
    source_type: Optional[str] = None      # e.g. "web", "book", "article", "dataset"
    language: Optional[str] = None         # language of the source, ISO 639-1

    # Provenance links
    supports_frames: List[str] = field(default_factory=list)
    supports_statements: List[str] = field(default_factory=list)
    contradicts_statements: List[str] = field(default_factory=list)

    # Arbitrary metadata
    extra: Dict[str, Any] = field(default_factory=dict)
```

Notes:

* `supports_frames` is a list of ids (e.g. event ids, frame ids) that this source underpins.
* `supports_statements` / `contradicts_statements` can reference finer-grained statement ids if you choose to model them.
* None of the fields here are language-specific; rendering “According to …” or a reference list is done by higher-level code.

### 5.3 Use with the frontend API

The core NLG API (`generate`, `generate_bio`, `NLGSession`) operates on individual frames.

Source frames are typically used in two ways:

1. **Inline attribution**
   A planner chooses to realize a `SourceCitationFrame` as an “according to X” clause or parenthetical (potentially using a dedicated construction). This is optional and domain-specific.
2. **Reference list output**
   After rendering an `ArticleDocumentFrame`, caller code (outside this repo) can walk `article.sources` and format a reference list using the metadata in `SourceCitationFrame`.

---

## 6. Integration patterns

### 6.1 Normalization from upstream JSON

Upstream components (e.g. an Abstract Wikipedia bridge) should:

1. Build base semantic objects (`Entity`, `TimeSpan`, `Event`, etc.).
2. Construct domain frames (`BioFrame`, event frames, relational frames).
3. Group those into `SectionSummaryFrame`s (possibly based on section tags in the source).
4. Wrap everything in a single `ArticleDocumentFrame`.
5. Build `SourceCitationFrame`s from reference metadata and attach them to the article.

The normalization layer is responsible for handling raw JSON idiosyncrasies; meta frames should only see clean, typed data.

### 6.2 Rendering in practice

For a given target language `lang`:

* A caller may ignore meta frames and call `generate(lang, frame)` directly on content frames; this is sufficient for single-sentence use cases.
* For full articles, a higher-level orchestrator should:

  * pick a section order from `article.sections`,
  * for each section, iterate over `section.frames` in an appropriate order,
  * call `generate(lang, frame)` on each, collecting sentences,
  * optionally interleave inline citations, headings, and list formatting.

The meta frames enable consistent orchestration across languages without hard-wiring wiki-specific details into the core NLG stack.

### 6.3 Debugging and QA

Because `ArticleDocumentFrame` knows about:

* the subject,
* all sections,
* all sources,

it can be used for:

* QA checks such as “every statement should have at least one supporting source”,
* comparing two article structures (e.g. two language editions),
* tracing which facts came from which upstream sources.

This fits into the broader QA story alongside lexicon regression tests and language-level test suites.

---

## 7. Extension guidelines

When extending meta frames:

* **Do** add fields that are:

  * language-independent,
  * stable across wiki projects,
  * clearly about document/section/source metadata.
* **Do not**:

  * add fields that encode concrete wiki markup or citation styles,
  * put language-specific strings here (beyond neutral labels and IDs),
  * mix meta-level fields into low-level semantic frames.

If a new feature requires per-language or per-wiki logic (e.g. exact “References” heading, template names, formatting rules), implement it in:

* the caller integration layer, or
* a small, separate adapter that consumes meta frames and produces wiki markup.

This keeps the core semantics and NLG components clean, portable, and testable across projects and languages.


