
# Frame Families Overview

This document describes the semantic frame families used by the Abstract Wiki Architect NLG stack. Frames are the main interface between Abstract Wikipedia–style semantics and the multilingual generation pipeline.

The goals are to:

* provide a small, explicit set of frame families that cover common encyclopedic content,
* keep frame structures language-neutral and data-driven,
* match the public NLG API (`generate`, `generate_bio`, `generate_event`, etc.).

---

## 1. Frames in the NLG API

At the API level, all frames implement a simple protocol:

```python
from typing import Protocol

class Frame(Protocol):
    frame_type: str  # e.g. "bio", "entity.person", "event.generic"
````

In the current implementation:

* The protocol lives in `semantics.types` (and is re-exported from `nlg.semantics`).
* Concrete frame classes live under `semantics/` (e.g. `semantics/entity/person_frame.py`,
  `semantics/event/generic_event_frame.py`, etc.).

The frontend API treats frames uniformly:

```python
# nlg.api (conceptual)
def generate(
    lang: str,
    frame: Frame,
    *,
    options: GenerationOptions | None = None,
    debug: bool = False,
) -> GenerationResult: ...
```

Specialized helpers simply fix the frame type: `generate_bio(lang, bio: BioFrame, ...)`,
`generate_event(lang, event: Event, ...)`, etc.

### 1.1 Current status

* `BioFrame` (`frame_type = "bio"`) is fully wired end-to-end through the router and family engines.
* `Event` (`frame_type = "event.generic"`) and other families are defined and normalized, but only some have complete realization engines; others are design targets that will be implemented incrementally.

All frame families described below define a stable taxonomy and expected structure so that semantics, normalization, and generation can evolve coherently.

---

## 2. Frame lifecycle (end-to-end)

At a high level, frame handling proceeds as follows:

1. **Abstract semantics in**

   * Upstream components (e.g. Abstract Wikipedia / Wikifunctions) provide JSON for one or more frames.
   * `semantics.aw_bridge` and `semantics.normalization` validate and convert this JSON into typed frame instances (e.g. `BioFrame`, `PersonFrame`, `Event`).

2. **Discourse and information structure**

   * `discourse/state.py` tracks discourse context.
   * `discourse/info_structure.py` assigns topic/focus labels.
   * `discourse/referring_expression.py` decides on pronouns vs. full NPs.
   * `discourse/planner.py` sequences multiple frames into multi-sentence plans (e.g. birth → profession → awards).

3. **Routing and realization**

   * `router.py` selects a family engine and language profile.
   * The engine maps frames to one or more **constructions** (e.g. copular, eventive, comparative) and calls the relevant morphology + lexicon components to realize surface forms.

4. **Aggregation and output**

   * The engine and discourse layer assemble tokens into sentences, apply punctuation, and return a `GenerationResult` with `text`, `sentences`, `lang`, and the original `frame`.

---

## 3. Design principles for frame families

All 58 frame families follow the same principles:

1. **Language-neutral semantics**

   * Fields describe *what* to say, not *how* to say it (no inflected strings).
   * Entities, times, quantities, and roles are structured objects, usually linked to Wikidata IDs when available.

2. **Stable `frame_type` keys (canonical vs aliases)**

   * Each family has a canonical string of the form:

     * `"bio"`
     * `"entity.*"` for entity-centric frames,
     * `"event.*"` for event-centric frames,
     * `"rel.*"` for relational frames,
     * `"narr.*"` for narrative frames,
     * `"meta.*"` for meta / wrapper frames.

     Examples: `"entity.person"`, `"event.generic"`, `"rel.definition"`, `"narr.timeline"`, `"meta.article"`.

   * These canonical keys are used by:

     * JSON input (`"frame_type": "entity.person"`),
     * normalization and routing,
     * CLI (`--frame-type entity.person`).

   * For compatibility, `semantics.aw_bridge` also accepts legacy *aliases* such as `"person"`, `"conflict-event"`, `"timeline"`, and normalizes them into the canonical dotted form. New code should always emit canonical names.

3. **Small, typed dataclasses**

   * For each family there is one main dataclass (e.g. `PersonFrame`) implementing the `Frame` protocol.
   * Additional internal helper types (e.g. `Participant`, `TimelineItem`) are used where needed.

4. **Clear ownership boundaries**

   * **Frames**: semantics, roles, and attributes.
   * **Discourse**: ordering, packaging into paragraphs, referring expressions.
   * **Constructions**: clause templates (copula, event, comparative, etc.).
   * **Morphology + lexicon**: inflection and lexical choice.

5. **Data-driven schemas**

   * Every frame family has a JSON schema (under `schemas/frames/…`) used both for validation and as public documentation of field structure.

---

## 4. Taxonomy of frame families

The final system groups frames into five broad categories:

* **Entity-centric frames** – summarize “things you can write a lead sentence about”.
* **Event-centric frames** – describe episodes in time.
* **Relational frames** – encode reusable binary/ternary facts (definition, membership, cause, etc.).
* **Narrative / aggregate frames** – sequence or aggregate multiple events/facts.
* **Meta / wrapper frames** – describe articles and sections as wholes.

Below is the canonical list of families and their intended `frame_type` keys.
Legacy aliases (e.g. `"person"`, `"generic-event"`) are accepted on input but always normalized to these forms.

### 4.0 Biographical frame

0. `bio`
   Biographical summary frame used as a high-level wrapper over one or more entity- and event-centric frames for a person.

### 4.1 Entity-centric frame families

These frames usually correspond to article subjects and first sentences.

1. `entity.person`
2. `entity.organization`
3. `entity.geopolitical_entity`
4. `entity.place` (non-political geographic feature)
5. `entity.facility` (buildings, infrastructure)
6. `entity.astronomical_object`
7. `entity.species` (and higher taxa)
8. `entity.chemical_material`
9. `entity.artifact` (physical object / object type)
10. `entity.vehicle`
11. `entity.creative_work` (book, film, painting, game, etc.)
12. `entity.software_protocol_standard`
13. `entity.product_brand`
14. `entity.sports_team`
15. `entity.competition_league`
16. `entity.language`
17. `entity.religion_ideology`
18. `entity.discipline_theory`
19. `entity.law_treaty_policy`
20. `entity.project_program`
21. `entity.fictional_entity` (character, universe, franchise)

Each of these frames typically holds:

* a main `Entity` (e.g. `main_entity: Entity`),
* key attributes (type, domain, dates, locations, membership sizes, etc.),
* optional auxiliary fields used by narrative frames (e.g. founding date reused by a timeline).

### 4.2 Event-centric frame families

These frames model temporally bounded episodes.

22. `event.generic`
23. `event.historical`
24. `event.conflict` (battle, war, operation)
25. `event.election` (election or referendum)
26. `event.disaster` (disaster / accident)
27. `event.scientific_milestone`
28. `event.cultural` (festival, premiere, exhibition, ceremony)
29. `event.sports` (match, season, tournament instance)
30. `event.legal_case`
31. `event.economic_financial` (crisis, merger, IPO, sanctions episode)
32. `event.exploration_mission` (exploration / expedition / mission)
33. `event.life` (education, appointment, award, marriage, relocation, etc.)

All event families refine a shared backbone:

* participants with typed roles,
* time spans,
* location(s),
* event-specific properties (scores, magnitudes, verdicts, etc.).

### 4.3 Relational / statement-level frame families

These frames encode reusable fact templates that can be inserted anywhere in an article.

34. `rel.definition` (definition / classification)
35. `rel.attribute` (simple property)
36. `rel.quantitative` (numeric/statistical fact)
37. `rel.comparative_ranking`
38. `rel.membership_affiliation`
39. `rel.role_position_office`
40. `rel.part_whole_composition`
41. `rel.ownership_control`
42. `rel.spatial_relation`
43. `rel.temporal_relation`
44. `rel.causal_influence`
45. `rel.change_of_state`
46. `rel.communication_statement`
47. `rel.opinion_evaluation`
48. `rel.relation_bundle` (small, multi-fact cluster for one subject)

Implementation-wise, many of these are thin, typed wrappers around more generic types (`Entity`, `Event`, `Quantity`, `TimeSpan`), plus role labels.

### 4.4 Narrative / aggregate frame families

These frames describe sequences and aggregates, usually spanning multiple sentences.

49. `narr.timeline` (chronology for a subject)
50. `narr.career_season_campaign_summary`
51. `narr.development_evolution` (changes over time)
52. `narr.reception_impact`
53. `narr.structure_organization` (internal structure of an entity)
54. `narr.comparison_set_contrast` (paragraph-level comparison)
55. `narr.list_enumeration` (enumerative descriptions)

These frames typically contain:

* a `subject` entity,
* ordered collections of subframes (e.g. events, relational frames),
* optional grouping into phases or sections.

### 4.5 Meta / wrapper frame families

These are not article content per se, but describe how content is packaged.

56. `meta.article`
57. `meta.section_summary`
58. `meta.source`

They are useful for:

* mapping Abstract Wikipedia article structures to concrete sections,
* summarizing sections into short leads,
* tracking provenance and citation requirements for generated statements.

---

## 5. Implementation layout (high-level)

The frames described above are implemented and wired across several layers:

* **Semantics** (`semantics/`)

  * `semantics.types`: core protocols and dataclasses (`Entity`, `Event`, `Frame`, `BioFrame`, etc.).
  * `semantics.normalization`: JSON → frame conversion, validation, and defaults.
  * `semantics.aw_bridge`: bridges from Abstract Wikipedia / Wikifunctions data formats and normalizes aliases.

* **NLG semantics API** (`nlg/semantics/__init__.py`)

  * Exposes `Frame`, `BioFrame`, `Event`, and the other frame classes to the rest of the NLG stack.

* **Frontend API** (`nlg/api.py`, `docs/FRONTEND_API.md`, `docs/Interfaces.md`)

  * Public entry points (`generate`, `generate_bio`, `generate_event`, `NLGSession`).

* **Discourse** (`discourse/`)

  * Planning, referring expressions, information structure, and packaging.

* **Router and engines** (`router.py`, `engines/*.py`, `language_profiles/profiles.json`)

  * Language routing, engine selection, and morphology/lexicon configuration.

---

## 6. Usage and extension guidelines

When adding or extending frame families:

1. **Decide the family and `frame_type`**

   * Choose the appropriate family from sections 4.0–4.5.
   * Introduce a new canonical `frame_type` only if no existing family fits.
   * If you need to support legacy aliases, add them to `semantics.aw_bridge` and normalize them to the new canonical string.

2. **Define the dataclass**

   * Add a typed dataclass in `semantics/` implementing `Frame`.
   * Ensure it uses existing primitives (`Entity`, `TimeSpan`, `Quantity`, etc.) where possible.
   * Set its `frame_type` class attribute to the canonical string (e.g. `"entity.person"`).

3. **Define the JSON schema**

   * Add a schema under `schemas/frames/…` documenting all fields and their types.
   * Use the canonical `frame_type` in schema examples and enums.

4. **Implement normalization**

   * Map incoming JSON (from AW / Z-objects) to the dataclass, applying defaults and light coercion.
   * Reject malformed input early with clear error messages.

5. **Wire up routing and realization**

   * Update the routing logic so `frame_type` → appropriate realization path.
   * Map each frame family to constructions that can express its facts in at least one sentence.

6. **Add tests and examples**

   * Provide unit tests for normalization and realization.
   * Add small example JSON snippets and expected outputs for major languages.

By following this taxonomy and workflow, all 58 frame families can be added and extended incrementally while keeping the overall API and architecture stable.


