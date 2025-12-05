
# Event frames (frame_type family `event.*`)

Event frames represent single events or episodes in time: things that happen to entities, at a time and optionally in a place, with some additional properties.

Event frames are used:

* inside biography frames (birth, death, awards, appointments),
* as standalone frames for historical events, discoveries, matches, etc.,
* as building blocks for timelines and richer narrative structures.

At runtime, the core generic event type is `semantics.types.Event`.  
In the public NLG API, this is aliased as `EventFrame`.

The canonical registry key for the generic event frame is `frame_type = "event.generic"`.  
Other event-family frames (e.g. `event.life`, `event.historical`, `event.sports`) are thin specializations that reuse the same underlying `Event` structure.

> Implementation status: the event-family frames (`event.*`) and the `generate_event` helper are wired at the API level but do not yet have a dedicated engine; callers should expect placeholder/empty output until an event engine is implemented.

---

## 1. Relationship to the codebase

### 1.1 Runtime types

Core semantic types:

* `semantics.types.Entity`
* `semantics.types.TimeSpan`
* `semantics.types.Location`
* `semantics.types.Event`
* `semantics.types.BioFrame` (which embeds `Event` for birth/death/other-events)

Event-family wrappers and specializations (non-exhaustive):

* `semantics.event.life_event_frame.LifeEventFrame` – biographical life events (`frame_type = "event.life"`).
* Other high-level event frames under `semantics.event.*` (historical, scientific milestone, sports, etc.) that either subclass `Event` or contain one or more `Event` instances as their core episodes.

Exported via `nlg.semantics`:

```python
from nlg.semantics import EventFrame  # alias for semantics.types.Event
````

### 1.2 Frontend API

Frontend helpers:

* `nlg.api.generate_event(lang: str, event: EventFrame, ...)`
* Generic `nlg.api.generate(lang: str, frame: Frame, ...)` with any event-family frame (i.e. `frame_type` starting with `"event."`, such as `"event.generic"`).

`EventFrame` participates in the common `Frame` protocol via the frame-type registry; its canonical key in the registry is `"event.generic"`.

---

## 2. Core data model (`semantics.types.Event`)

### 2.1 Fields

The semantic event object has the following fields (Python-level):

* `id: Optional[str]`

  * Stable identifier for the event, if available (e.g. a Wikidata QID, timeline ID, or local ID).

* `event_type: str`

  * High-level label for the event, e.g. `"birth"`, `"death"`, `"discovery"`, `"award"`, `"generic"`.
  * Inventory is intentionally open; projects can define their own controlled vocabularies.

* `participants: dict[str, Entity]`

  * Mapping from role label to `Entity`.
  * Example:

    ```python
    {
        "subject": Entity(...),
        "object": Entity(...),
        "beneficiary": Entity(...),
    }
    ```

* `time: TimeSpan | None`

  * Optional time span describing when the event occurred.

* `location: Location | None`

  * Optional location where the event took place.

* `properties: dict[str, Any]`

  * Arbitrary additional semantic properties (instrument, manner, cause, etc.).

* `extra: dict[str, Any]`

  * Arbitrary metadata (original source structures, debug info, etc.).

### 2.2 Supporting types (Entity, TimeSpan, Location)

This document does not redefine the full schemas for `Entity`, `TimeSpan`, and `Location`; see `semantics.types` for details. At a high level:

* `Entity` represents people, organizations, places, works, etc., with fields like `id`, `name`, `human`, `gender`, `entity_type`, and flexible `features` / `extra` maps.
* `TimeSpan` represents partial or full dates and intervals (e.g. year only, year-month-day, start/end).
* `Location` represents named places with at least a `name` and optional classification (`kind`), codes, and feature maps.

All three are designed to be tolerant of partial data and to accept additional unknown fields via `extra`/`features`.

---

## 3. JSON representation

### 3.1 Top-level shape

The canonical JSON shape for a *generic* event frame (as seen by external callers, CLI, or bridges) is:

```json
{
  "frame_type": "event.generic",

  "id": "E1",
  "event_type": "birth",

  "participants": {
    "subject": {
      "id": "Q7186",
      "name": "Marie Curie",
      "entity_type": "person",
      "human": true
    }
  },

  "time": {
    "start_year": 1867,
    "start_month": 11,
    "start_day": 7
  },

  "location": {
    "name": "Warsaw",
    "kind": "city",
    "country_code": "PL"
  },

  "properties": {
    "parents": [
      { "id": "Q", "name": "Bronisława Skłodowska" },
      { "id": "Q", "name": "Władysław Skłodowski" }
    ]
  },

  "extra": {
    "source": "wikidata",
    "original_ids": ["Q7186", "Q", "Q"]
  }
}
```

Required top-level keys:

* `frame_type`
  Must be an event-family key (string starting with `"event."`), typically `"event.generic"` for bare `Event` instances. Other specializations such as `"event.life"` reuse the same underlying fields.

Optional but strongly recommended:

* `event_type`
* `participants`
* `time` or `location` (at least one)
* `properties`
* `extra`

### 3.2 `participants` object

`participants` is a JSON object:

```json
"participants": {
  "<role-label>": <entity-spec>,
  "...": ...
}
```

* Keys are role labels (`"subject"`, `"object"`, `"agent"`, `"patient"`, `"recipient"`, etc.).
* Values are `Entity`-shaped objects; minimally:

  ```json
  {
    "name": "Marie Curie"
  }
  ```

  with optional IDs, type hints, features, etc.

Role labels are free-form strings and may be normalized internally. See §4 for recommended labels.

### 3.3 `time` object

`time` follows the `TimeSpan` semantics, encoded as a flat JSON object. Typical patterns:

* Single day:

  ```json
  "time": {
    "start_year": 1867,
    "start_month": 11,
    "start_day": 7
  }
  ```

* Year only:

  ```json
  "time": {
    "start_year": 1898
  }
  ```

* Interval:

  ```json
  "time": {
    "start_year": 1914,
    "end_year": 1918
  }
  ```

Additional flags like `approximate`, `precision`, or calendar-specific markers can be included as extra fields.

### 3.4 `location` object

`location` follows the `Location` semantics, e.g.:

```json
"location": {
  "name": "Paris",
  "kind": "city",
  "country_code": "FR"
}
```

Optional suggestions:

* `kind`: `"city"`, `"country"`, `"region"`, `"building"`, `"institution"`, etc.
* `admin_hierarchy`: list of enclosing units.
* Any additional geographic codes in `features` / `extra`.

### 3.5 `properties` object

`properties` is a free-form map of additional semantic slots. Typical examples:

```json
"properties": {
  "instrument": {
    "name": "X-ray apparatus"
  },
  "manner": "secretly",
  "cause": "apparent radiation exposure",
  "tense": "past",
  "verb_lemma": "discover"
}
```

Conventions:

* Use entity-shaped objects whenever the value is an entity (instrument, cause-event, etc.).
* Use plain strings or scalars for simple attributes (manner, degree, numeric counts).
* Reserve a small number of well-known keys (see §5.2 and §5.3) and allow project-specific keys in addition.

### 3.6 `extra` object

`extra` is for metadata that is not part of semantic content:

* original AW / Z-notation fragments,
* Wikidata IDs and statements,
* debugging flags,
* provenance info.

Tools and engines must ignore unknown keys in `extra`.

---

## 4. Participant role labels

`participants` keys are free-form strings. For interoperability, use a small canonical set where possible:

Core roles:

* `subject`

  * Main entity the event is “about” (often the grammatical subject).

* `agent`

  * Deliberate initiator of the action (if different from `subject`).

* `patient`

  * Entity that undergoes change; roughly the thing affected.

* `theme`

  * Entity that is moved, transferred, or discussed.

* `recipient`

  * Entity that receives something.

* `beneficiary`

  * Entity that benefits from the event.

* `co_participant`

  * Entity that participates symmetrically with the subject (e.g. marriage partner, co-author).

Locative / temporal roles:

* `source`
* `goal`
* `path`

These can be represented either as participants (with `Entity`-like locations) or via `location` + properties; choose one convention per project.

Causal / other roles:

* `cause`
* `result`
* `instrument`
* `stimulus` (for perception/experience events)
* `experiencer`

Guidelines:

* Use lowercase, snake_case labels.
* Use one label per participant role; if multiple entities share the role, use a list in `properties` (e.g. `properties.parents`) or multiple participants (`co_participant_1`, `co_participant_2`) depending on your style.
* Do not encode lexical items into role names (avoid `"teacher"`, `"student"`); keep them semantic (`"agent"`, `"recipient"`).

---

## 5. Event type conventions (`event_type`)

`event_type` is an open string field. This section recommends a small shared inventory with suggested minimal slots. Projects may extend it as needed.

The recommendations below apply both to bare `Event` instances (`frame_type: "event.generic"`) and to families that embed an `Event` in a field like `main_event` (e.g. scientific milestones, historical events, life events).

### 5.1 Biographical core

Recommended event types for biographies:

* `"birth"`

  * Required:

    * `participants.subject` (entity being born)

  * Recommended:

    * `time` (date of birth)
    * `location` (place of birth)
    * `properties.parents` (list of entities)

* `"death"`

  * Required:

    * `participants.subject`

  * Recommended:

    * `time` (date of death)
    * `location` (place of death)
    * `properties.cause` (string or entity)

* `"appointment"`

  * Required:

    * `participants.subject` (appointee)
    * `properties.position` (entity or string)

  * Recommended:

    * `participants.organization` (employer/body)
    * `time` (start date)

* `"award"`

  * Required:

    * `participants.recipient`
    * `properties.award` (entity or string)

  * Recommended:

    * `time`
    * `participants.organization` (awarding body)

* `"education"`

  * Recommended:

    * `participants.subject`
    * `participants.institution`
    * `properties.field` (field of study)
    * `time`

* `"marriage"`

  * Recommended:

    * `participants.subject`
    * `participants.co_participant` (spouse)
    * `time`
    * `location`

These event types are typically embedded inside biographical frames (e.g. via `LifeEventFrame` or as events inside `BioFrame`) as `birth_event`, `death_event`, or appended to `other_events`.

### 5.2 Scientific / technical events

Canonical examples:

* `"discovery"`

  * `participants.agent` (discoverer)
  * `participants.theme` (thing discovered)
  * `time`, `location` optional.

* `"invention"`

  * `participants.agent`
  * `participants.theme` (invention)
  * `time`, `location`.

* `"publication"`

  * `participants.agent` (author or team)
  * `participants.work` (publication)
  * `time`.

These are especially relevant for `event.scientific_milestone`-style frames where `main_event` is an `Event`.

### 5.3 Historical / political events

Examples:

* `"founding"`

  * `participants.subject` (entity founded: party, organization, city)
  * `participants.agent` or `properties.founders` (list) as needed
  * `time`, `location`.

* `"treaty_signing"`

  * `participants.parties` (list in `properties` or separate participants)
  * `properties.treaty` (entity)
  * `time`, `location`.

* `"election"`

  * `properties.office`
  * `properties.jurisdiction`
  * `time` (date or period)
  * participants for winners and main candidates.

* `"battle"`

  * `properties.conflict` (war/operation)
  * `participants.side_a`, `participants.side_b`
  * `time`, `location`.

Full-fledged war/conflict/treaty frame families can be defined on top of `Event` if needed, but simple summaries can already be expressed via a single event frame.

### 5.4 Generic clause-like events

For generic “verb + arguments” realizations:

* `"generic_intransitive"`

  * `participants.subject`
  * `properties.verb_lemma` (e.g. `"arrive"`)
  * Optional: `time`, `location`, `properties.manner`, `properties.tense`, `properties.aspect`, etc.

* `"generic_transitive"`

  * `participants.subject`
  * `participants.object`
  * `properties.verb_lemma`
  * Optional tense/aspect/polarity/voice in `properties`.

These generic event types are intended to map to constructions like `INTRANSITIVE_EVENT` and `TRANSITIVE_EVENT`, which expect slots such as `subject`, `object`, and `verb_lemma`.

---

## 6. Building event frames (step-by-step)

General procedure for constructing an `EventFrame` (i.e. an `Event` with `frame_type` in the `event.*` family, typically `"event.generic"`):

1. **Choose `event_type`**

   * Prefer a stable value from a project-specific inventory (e.g. `"birth"`, `"award"`, `"discovery"`, `"generic_transitive"`).

2. **Identify participants and assign roles**

   * Determine the main entities and assign them canonical role labels (`subject`, `agent`, `patient`, `recipient`, etc.).
   * Represent each participant as an `Entity`-shaped JSON object.

3. **Fill `time` and `location`**

   * Use a `TimeSpan`-shaped object for dates / intervals.
   * Use a `Location`-shaped object for places.

4. **Add properties**

   * Include lexical information where needed, e.g. `properties.verb_lemma`, `properties.tense`, `properties.aspect`.
   * Add additional semantic slots such as `instrument`, `manner`, `cause`, etc.

5. **Set `id` (optional but recommended)**

   * Use a stable identifier from the upstream knowledge base if possible.

6. **Attach metadata in `extra`**

   * Include original Z-objects, Wikidata statements, provenance, or debugging info here rather than inventing new top-level fields.

7. **Validate**

   * Ensure `frame_type` is in the `event.*` family (typically `"event.generic"` for bare `Event` instances).
   * Ensure the event has at least one meaningful participant or a time/location; empty skeletons should be avoided.

---

## 7. Examples

### 7.1 Birth event for a biography

```json
{
  "frame_type": "event.generic",
  "id": "E_birth_Q7186",
  "event_type": "birth",

  "participants": {
    "subject": {
      "id": "Q7186",
      "name": "Marie Curie",
      "entity_type": "person",
      "human": true,
      "gender": "female"
    }
  },

  "time": {
    "start_year": 1867,
    "start_month": 11,
    "start_day": 7
  },

  "location": {
    "name": "Warsaw",
    "kind": "city",
    "country_code": "PL"
  },

  "properties": {
    "parents": [
      { "id": "Q", "name": "Bronisława Skłodowska" },
      { "id": "Q", "name": "Władysław Skłodowski" }
    ]
  }
}
```

Embedded into a `BioFrame`:

```json
{
  "frame_type": "bio",
  "main_entity": { "id": "Q7186", "name": "Marie Curie", "human": true },
  "primary_profession_lemmas": ["physicist"],
  "nationality_lemmas": ["polish"],
  "birth_event": { "...": "as above" }
}
```

(A biographical specialization such as `LifeEventFrame` would use the same `Event` fields but may declare a more specific `frame_type` like `"event.life"`.)

### 7.2 Transitive discovery event

```json
{
  "frame_type": "event.generic",
  "id": "E_discovery_Q7186_radium",
  "event_type": "discovery",

  "participants": {
    "agent": {
      "id": "Q7186",
      "name": "Marie Curie",
      "entity_type": "person"
    },
    "theme": {
      "id": "Q11399",
      "name": "radium",
      "entity_type": "chemical_element"
    }
  },

  "time": {
    "start_year": 1898
  },

  "location": {
    "name": "Paris",
    "kind": "city",
    "country_code": "FR"
  },

  "properties": {
    "verb_lemma": "discover",
    "tense": "past",
    "manner": "independently"
  }
}
```

An event engine can map this to a `TRANSITIVE_EVENT` construction with:

```python
slots = {
    "subject": participants["agent"],
    "object": participants["theme"],
    "verb_lemma": properties["verb_lemma"],
    "tense": properties.get("tense", "past"),
}
```

---

## 8. Summary

* `EventFrame` is the generic event semantic type, implemented as `semantics.types.Event` and exported via `nlg.semantics`.
* The JSON representation consists of a required `frame_type` in the `event.*` family (typically `"event.generic"`) plus `event_type`, `participants`, `time`, `location`, `properties`, and `extra`.
* Participants are named by role labels mapped to `Entity` objects; a small shared inventory of role labels improves interoperability.
* `event_type` is an open string field; this document recommends a core set for biographical, scientific, and historical use-cases.
* Generic “clause-like” events are supported via properties like `verb_lemma`, aligning with constructions such as `TRANSITIVE_EVENT`.


