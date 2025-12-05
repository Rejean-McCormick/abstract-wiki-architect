Here is an updated version of `docs/FRAMES_NARRATIVE.md` consistent with the current narrative frame classes and canonical `frame_type` strings (`aggregate.timeline`, `aggregate.career_summary`, `aggregate.development`, `reception-impact`, `narr.structure-organization`, `narr.comparison-set-contrast`, `aggregate.list`):

---

# Narrative and aggregate frames

This document specifies the narrative / aggregate frame families used to represent multi-sentence structures (items 49–55 in the global frame inventory). These frames sit on top of the core semantic types in `semantics/types.py` (`Entity`, `Location`, `TimeSpan`, `Event`, `BioFrame`) and feed into `discourse/planner.py` for multi-sentence planning.

The concrete dataclasses live under `semantics/narrative/*.py` and are registered in `semantics/all_frames.py`. They expose stable canonical `frame_type` strings:

* `aggregate.timeline`
* `aggregate.career_summary`
* `aggregate.development`
* `reception-impact`
* `narr.structure-organization`
* `narr.comparison-set-contrast`
* `aggregate.list`

They are **language-agnostic**: no surface forms, no language-specific word order. All linguistic realization is delegated to the usual stack (discourse → constructions → morphology → engines) described in `docs/ARCHITECTURE.md`.

---

## 1. Scope

Narrative / aggregate frames cover:

* `TimelineChronologyFrame` (`frame_type="aggregate.timeline"`)
  Ordered sequence of events for a subject (person, organization, conflict, project…).

* `CareerSeasonCampaignSummaryFrame` (`frame_type="aggregate.career_summary"`)
  Specialized summary timeline for one coherent trajectory (career, sports season, political campaign).

* `DevelopmentEvolutionFrame` (`frame_type="aggregate.development"`)
  Staged evolution of an entity or concept over time.

* `ReceptionImpactFrame` (`frame_type="reception-impact"`)
  Critical/public reception and broader impact of a work, idea, event, or project.

* `StructureOrganizationFrame` (`frame_type="narr.structure-organization"`)
  Internal structure of an entity (organization, government, system, document).

* `ComparisonSetContrastFrame` (`frame_type="narr.comparison-set-contrast"`)
  Comparison or contrast of multiple entities along shared dimensions.

* `ListEnumerationFrame` (`frame_type="aggregate.list"`)
  Enumerations: “X has A, B, and C”, “The main types are…”.

These frames are designed to be consumed by the same frontend API (`generate`, `generate_event`, `NLGSession`) as other frames once engines exist for them.

---

## 2. Design principles

Narrative frames follow the general semantic frame guidelines used elsewhere in the project:

1. **Language-agnostic structure**

   * Only concepts like entities, events, time spans, and roles appear.
   * No strings that are specific to a language (no “was born”, “however”, etc.).
   * All free text is optional and treated as hints, not as required surface.

2. **Simple data classes**

   * Each frame is a plain, serializable record (dataclass-style).
   * Pointers to core types (`Entity`, `Event`, `TimeSpan`) are preferred over duplicating fields.

3. **Stable `frame_type` values**

   * Every frame declares a stable `frame_type` string, such as:

     * `aggregate.timeline`
     * `aggregate.career_summary`
     * `aggregate.development`
     * `reception-impact`
     * `narr.structure-organization`
     * `narr.comparison-set-contrast`
     * `aggregate.list`
   * The planner and engines dispatch on these values the same way they do for `BioFrame` and event frames.

4. **Planner-friendly**

   * Narrative frames expose:

     * a **subject** (one main entity or concept),
     * an optional **overall time span**,
     * a list of **items** (events, phases, components, compared items, list items),
     * optional **ordering / grouping hints** (e.g. “chronological”, “importance”, “phase N”).
   * `discourse/planner.py` can break them into per-sentence micro-frames, assign information structure, and route each to the right constructions/engine.

5. **Soft constraints, no logic**

   * Frames store facts, IDs, and hints.
   * They do **not** implement logic for sorting, filtering, or deduplication; that belongs in normalization and planning.

---

## 3. Common building blocks

All narrative frames are expected to reuse the following types from `semantics/types.py`:

* `Entity` – people, organizations, places, etc.
* `Location` – places with optional kind and country.
* `TimeSpan` – start/end years and optional month/day, with an `approximate` flag.
* `Event` – generic event with `event_type`, `participants`, `time`, `location`, and `properties`.

On top of those, narrative frames typically introduce:

* **Subject reference**

  * Either a full `subject: Entity | None` (e.g. for timelines, development frames), or
  * an identifier `subject_id: str | None` (e.g. for career / season summaries), which links to a separate entity frame.

* **Overall time span**

  * `overall_span: TimeSpan | None` or `overall_time_span: TimeSpan | None` – the overall window for the narrative.

* **Item lists**

  Per-frame item record types, e.g.:

  ```python
  @dataclass
  class TimelineEntry:
      event: Event
      label: str | None = None          # optional short label like "Early life"
      time_span: TimeSpan | None = None
      phase: str | None = None          # grouping into phases, if any
      salience: float = 1.0             # relative importance weight
  ```

  The exact item dataclass is per frame, but the pattern is the same: reference a core object (`Event`, `Entity`) plus small metadata.

* **Ordering / grouping hints**

  * `ordering: str | None` (e.g. `"chronological"`, `"reverse-chronological"`, `"importance"`, `"ranking"`).
  * Optional `phases`, `sections`, or hierarchy fields depending on the frame.

These structures are purely semantic; the planner decides how many sentences to realize and in which order.

---

## 4. Frame catalog

The shapes below are “recommended” / typical. The actual dataclasses in `semantics/narrative/*.py` are the source of truth and may include additional fields (attributes, metadata, etc.).

### 4.1 `TimelineChronologyFrame` (`frame_type="aggregate.timeline"`)

**Purpose**

Chronological sequence of events involving one main subject (a person, organization, city, project, conflict, etc.). Typical uses:

* “In 1891, Curie moved to Paris. In 1903, she shared the Nobel Prize in Physics…”
* “The war began in 1914 and ended in 1918…”

**Recommended fields**

```python
@dataclass
class TimelineChronologyFrame(Frame):
    frame_type: str = "aggregate.timeline"

    subject: Entity | None = None         # main entity the timeline is about
    overall_span: TimeSpan | None = None  # overall period, optional
    entries: list[TimelineEntry] = field(default_factory=list)

    # Optional hints
    ordering: str | None = "chronological"  # or "reverse-chronological"
    grouping_hint: str | None = None        # e.g. "by_phase"
    headline: str | None = None             # short label, e.g. "Timeline"
    extra: dict[str, Any] = field(default_factory=dict)
```

Where:

```python
@dataclass
class TimelineEntry:
    event: Event                     # full event semantics
    label: str | None = None         # optional label, e.g. "Early life"
    time_span: TimeSpan | None = None
    phase: str | None = None         # to group into phases/periods
    salience: float = 1.0            # relative importance
    extra: dict[str, Any] = field(default_factory=dict)
```

**Generation behavior (informal)**

* Planner sorts `entries` by `time_span` / `event.time` (or explicit `ordering` hints).
* Groups into phases if `phase` is used, optionally mapping phases to headings or lead sentences.
* Emits a sequence of event-level sentences (typically via an event engine) with temporal connectives chosen by discourse logic.

---

### 4.2 `CareerSeasonCampaignSummaryFrame` (`frame_type="aggregate.career_summary"`)

**Purpose**

Specialized timeline for one coherent trajectory:

* a person’s career,
* a sports club’s season,
* a political campaign or term in office.

Helps generate compact summaries like:

* “Over a career spanning four decades, X wrote more than fifty novels…”
* “In the 2020–21 season, the club finished second in the league and reached the cup final.”

**Recommended fields**

```python
@dataclass
class CareerSeasonCampaignSummaryFrame(Frame):
    frame_type: str = "aggregate.career_summary"

    subject_id: str | None = None
    domain: str | None = None          # "literature", "football", "politics", ...
    span: TimeSpan | None = None       # overall period
    phases: list[CareerPhase] = field(default_factory=list)

    # Summary metrics, domain-specific but language-agnostic
    metrics: dict[str, Any] = field(default_factory=dict)  # e.g. {"books_published": 50}
    headline: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class CareerPhase:
    label: str                         # "Early career", "Prime", "Later career"
    span: TimeSpan | None = None
    key_events: list[Event] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
```

**Generation behavior (informal)**

* Planner may realize one sentence per phase plus an overall summary sentence using `metrics`.
* Typical structures: “During his early career…”, “In her final seasons…”, “Overall, he scored 200 goals in 400 appearances.”

---

### 4.3 `DevelopmentEvolutionFrame` (`frame_type="aggregate.development"`)

**Purpose**

Describe how an entity or concept changes over time (city growth, product versions, theory development, institutional reforms).

**Recommended fields**

```python
@dataclass
class DevelopmentEvolutionFrame(Frame):
    frame_type: str = "aggregate.development"

    subject_id: str | None = None
    span: TimeSpan | None = None             # overall evolution period
    stages: list[DevelopmentStage] = field(default_factory=list)

    driving_factors: list[str] = field(default_factory=list)  # e.g. ["industrialization", "migration"]
    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class DevelopmentStage:
    label: str                                # "Founding", "Industrial expansion", ...
    span: TimeSpan | None = None
    summary_properties: dict[str, Any] = field(default_factory=dict)
    key_events: list[Event] = field(default_factory=list)
```

**Generation behavior (informal)**

* Planner orders `stages` by `span.start_year`.
* Typical templates:

  * “Initially, X was a small fishing village…”
  * “In the late 19th century, it industrialized…”
  * “Since the 1990s, it has become a major tourist destination…”

---

### 4.4 `ReceptionImpactFrame` (`frame_type="reception-impact"`)

**Purpose**

Capture reception and impact of a work, idea, event, policy, or product. Used for “Reception”, “Legacy”, “Impact” sections.

**Recommended fields**

```python
@dataclass
class ReceptionImpactFrame(Frame):
    frame_type: str = "reception-impact"

    subject_id: str | None = None

    # Reception
    critical_reception: list[ReceptionItem] = field(default_factory=list)
    public_reception: list[ReceptionItem] = field(default_factory=list)

    # Impact / legacy
    impact_domains: list[ImpactDomain] = field(default_factory=list)

    # Optional quantitative or categorical metrics
    metrics: dict[str, Any] = field(default_factory=dict)  # e.g. {"box_office_usd": 100_000_000}
    awards: list[Event] = field(default_factory=list)      # award events as `Event(event_type="award", ...)`

    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class ReceptionItem:
    source_entity: Entity | None = None      # critic, publication, community
    stance: str | None = None               # "positive", "mixed", "negative"
    topic: str | None = None                # "performance", "script", "visuals"
    time: TimeSpan | None = None
    properties: dict[str, Any] = field(default_factory=dict)  # e.g. {"quote_id": "..."}
```

```python
@dataclass
class ImpactDomain:
    domain: str                              # "physics", "cinema", "civil rights"
    description_properties: dict[str, Any] = field(default_factory=dict)
    key_events: list[Event] = field(default_factory=list)     # citations, adoptions, remakes, etc.
```

**Generation behavior (informal)**

* Planner clusters `ReceptionItem`s and `ImpactDomain`s into 1–3 sentences, typically:

  * “The film received positive reviews from critics, who praised X but criticized Y.”
  * “The theory has had a lasting impact on Z, influencing A and B.”
* If `awards` or numerical `metrics` are present, they are woven into the narrative (e.g. box office, prize names).

---

### 4.5 `StructureOrganizationFrame` (`frame_type="narr.structure-organization"`)

**Purpose**

Describe the internal structure of an entity: organization, government, academic department, large project, or even a document.

**Recommended fields**

```python
@dataclass
class StructureOrganizationFrame(Frame):
    frame_type: str = "narr.structure-organization"

    subject_id: str | None = None

    units: list[StructuralUnit] = field(default_factory=list)
    relations: list[StructuralRelation] = field(default_factory=list)

    # Optional hints for how detailed the description should be
    focus_level: str | None = None          # "top-level", "mid-level", "fine-grained"

    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class StructuralUnit:
    id: str
    label: str                               # "Board of Directors", "Senate", "Research Division"
    kind: str | None = None                  # "board", "committee", "department", ...
    parent_id: str | None = None             # hierarchical parent, if any
    role_description: dict[str, Any] = field(default_factory=dict)  # responsibilities, scope, etc.
```

```python
@dataclass
class StructuralRelation:
    source_id: str
    target_id: str
    relation_type: str                       # "reports-to", "elects", "oversees", "includes"
    properties: dict[str, Any] = field(default_factory=dict)
```

**Generation behavior (informal)**

* Planner reconstructs a simplified hierarchy from `units` and `relations`.
* Typical output:

  * “The university is governed by a board of trustees, which appoints the president.”
  * “The ministry is organized into three main departments: A, B, and C.”

---

### 4.6 `ComparisonSetContrastFrame` (`frame_type="narr.comparison-set-contrast"`)

**Purpose**

Express comparisons or contrasts between multiple entities:

* “X, Y, and Z are the three largest cities in A.”
* “Unlike X, Y is predominantly rural.”

**Recommended fields**

```python
@dataclass
class ComparisonSetContrastFrame(Frame):
    frame_type: str = "narr.comparison-set-contrast"

    scope: str | None = None                 # "in France", "within the EU", "in the dataset"
    metric: str | None = None                # "population", "GDP", "height", "area"
    ordering: str | None = None              # "descending", "ascending", "none"
    comparison_type: str | None = None       # "ranking", "contrast", "similarity"

    items: list[ComparisonItem] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class ComparisonItem:
    entity: Entity
    rank: int | None = None                  # 1, 2, 3, ...
    value: Any | None = None                 # numeric or categorical value for metric
    properties: dict[str, Any] = field(default_factory=dict)  # other descriptors
```

**Generation behavior (informal)**

* Planner sorts `items` by `rank` or `value` if provided.
* Typical patterns:

  * “X is the largest city in A, followed by Y and Z.”
  * “While X is heavily industrialized, Y remains primarily agricultural.”

---

### 4.7 `ListEnumerationFrame` (`frame_type="aggregate.list"`)

**Purpose**

Generic list / enumeration structure, used when the content is naturally presented as a list, but still needs to be realized as sentences:

* “X produces A, B, and C.”
* “The main types of Y are A, B, and C.”

**Recommended fields**

```python
@dataclass
class ListEnumerationFrame(Frame):
    frame_type: str = "aggregate.list"

    subject_id: str | None = None
    list_kind: str | None = None             # "features", "members", "subtypes", ...
    ordering: str | None = None              # "none", "importance", "alphabetical", ...
    scope: str | None = None                 # optional domain qualifier

    items: list[ListItem] = field(default_factory=list)

    # Optional hints
    preferred_realization: str | None = None # "single-sentence", "multi-sentence", "bulleted"
    extra: dict[str, Any] = field(default_factory=dict)
```

```python
@dataclass
class ListItem:
    entity: Entity | None = None             # if the item is an entity
    label: str | None = None                 # otherwise a label/lemma
    properties: dict[str, Any] = field(default_factory=dict)  # e.g. {"role": "captain"}
    salience: int | None = None
```

**Generation behavior (informal)**

* For short lists, planner prefers a single sentence with coordination (“A, B, and C”).
* For longer or complex lists, planner may split into multiple sentences or bullet-style enumerations (if the caller’s context allows it).

---

## 5. Planner and engine integration

At the system level, narrative frames fit into the same pipeline described in `docs/ARCHITECTURE.md` and `docs/FRONTEND_API.md`:

1. **Input**

   * A frontend client or AW bridge passes a narrative frame (one of the types above) to `generate` / `NLGSession.generate`.

2. **Normalization**

   * A narrative-specific normalizer ensures field consistency, fills in missing `TimeSpan`/`Event` structures where possible, and applies default ordering.

3. **Discourse planning**

   * `discourse/planner.py` treats the narrative frame as a container of **micro-frames** (event facts, comparisons, list items).
   * For each micro-frame, it derives sentence-level frames (e.g. event or biographical frames) and information structure hints, similar to how biographies are currently sequenced by `BIO_FRAME_ORDER`.

4. **Sentence realization**

   * Micro-frames are passed to the existing engine stack (once those engines are extended beyond biographies) and realized via constructions and morphology.

5. **Aggregation**

   * The planner concatenates the resulting sentences in the order determined by the narrative frame and discourse heuristics, filling `GenerationResult.sentences` and `GenerationResult.text`.

---

## 6. Status and roadmap

* The **biography pipeline** (`BioFrame` → text) is fully implemented and wired into the router and engines.
* Narrative frames and `EventFrame` are currently **API- and schema-level specifications**: they define the data model that future normalizers, planners, and engines will support.
* Implementations can proceed incrementally:

  * Start with `TimelineChronologyFrame` and `ListEnumerationFrame` (they reuse `Event` and simple entity lists).
  * Add domain-specific logic for `CareerSeasonCampaignSummaryFrame` and `ReceptionImpactFrame`.
  * Extend planner heuristics and constructions as needed.

---

## 7. Related documents and modules

* `docs/ARCHITECTURE.md` – high-level system architecture and end-to-end flow.
* `docs/FRONTEND_API.md`, `docs/Interfaces.md` – frontend API, `generate`, `generate_bio`, `generate_event`, `NLGSession`.
* `semantics/types.py` – core semantic types (`Entity`, `Location`, `TimeSpan`, `Event`, `BioFrame`).
* `semantics/narrative/*.py` – concrete dataclasses for narrative / aggregate frames and their canonical `frame_type` values.
* `semantics/all_frames.py` – global frame registry and frame family inventory.
* `discourse/planner.py` – multi-sentence planning and frame sequencing for biographies, to be extended for narrative frames.
