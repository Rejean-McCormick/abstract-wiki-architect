
# Frontend API

This document describes the simple frontend API for generating text from semantic frames.

The goal is to provide a small, stable set of entry points for integrators and linguists, while keeping the internal routing, engines, morphology, constructions, discourse, and lexicon modules as implementation details.

Frame families, canonical `frame_type` strings, and their fields are specified in the `docs/FRAMES_*.md` documents and corresponding JSON schemas under `schemas/frames/`.

> **Current implementation status**
>
> - The **person / biography pipeline** (via `BioFrame` / `PersonFrame`, `frame_type="bio"`) is fully wired end-to-end through the router and family engines.
> - `Event` / `EventFrame` (`frame_type="event.generic"`) and other frame families are **API-level placeholders**: they are defined and normalized, but many do not yet have concrete realization engines. Until engines are wired for a frame family, calls are expected to return empty strings or very minimal output.

---

## 1. Concepts

**Language (`lang`)**  
ISO 639-1 language code, e.g. `"en"`, `"fr"`, `"sw"`.

**Frame (`Frame`)**  
Semantic object representing what should be expressed (e.g. `PersonFrame`, `BioFrame`, `Event`, `PlaceFrame`, various entity / relation / timeline frames). Frames are grouped into *frame families* (biography, entity, event, relation, etc.), but the frontend API treats them uniformly.

Public protocol:

```python
from nlg.semantics import Frame

class Frame(Protocol):
    frame_type: str  # e.g. "bio", "entity.organization", "event.generic", "rel.membership"
````

Concrete frame classes live under `semantics/…` and implement this protocol.

**Frame family**
Coherent group of related frame types with similar semantics and target constructions, for example:

* biography / person-centric frames,
* entity-centric frames (places, organizations, works, etc.),
* event-centric frames (wars, elections, disasters, etc.),
* relational frames (membership, office-holding, part–whole, etc.),
* temporal / aggregate frames (timelines, seasons, careers, etc.),
* meta frames (article / section summaries, citation metadata).

Each individual frame is a small dataclass (or equivalent) implementing `Frame` and carrying a `frame_type` string that identifies its family and subtype. The intended inventory and canonical `frame_type` strings are described in detail in:

* `docs/FRAMES_OVERVIEW.md`
* `docs/FRAMES_ENTITY.md`
* `docs/FRAMES_EVENT.md`
* `docs/FRAMES_RELATIONAL.md`
* `docs/FRAMES_NARRATIVE.md`
* `docs/FRAMES_META.md`

**Generation options (`GenerationOptions`)**
Optional high-level controls (style, length, discourse mode, etc.).

**Generation result (`GenerationResult`)**
Structured output containing the realized text and metadata.

---

## 2. Quick start

Assuming the package name is `nlg` and you are using the person / biography pipeline.

Canonical public imports:

```python
from nlg.api import generate_bio
from nlg.semantics import BioFrame  # or EventFrame, Frame
from semantics.types import Entity  # entity model
```

Example:

```python
bio = BioFrame(
    main_entity=Entity(name="Douglas Adams", gender="male", human=True),
    primary_profession_lemmas=["writer"],
    nationality_lemmas=["British"],
)

result = generate_bio(lang="en", bio=bio)

print(result.text)       # "Douglas Adams was a British writer."
print(result.sentences)  # ["Douglas Adams was a British writer."]
```

You can also use the more explicit alias `PersonFrame` (a thin subclass of `BioFrame` with `frame_type="bio"`):

```python
from semantics.entity.person_frame import PersonFrame

person = PersonFrame(
    main_entity=Entity(name="Douglas Adams", gender="male", human=True),
    primary_profession_lemmas=["writer"],
    nationality_lemmas=["British"],
)
result = generate_bio("en", person)
```

Generic entry point:

```python
from nlg.api import generate
from semantics.types import BioFrame, Entity

bio = BioFrame(
    main_entity=Entity(name="Douglas Adams", gender="male", human=True),
    primary_profession_lemmas=["writer"],
)

result = generate(lang="fr", frame=bio)
print(result.text)
```

> **Note:** At the moment, the generic path for `frame_type="bio"` is effectively backed by the biography engine via the router. Other frame families (e.g. event, relation, timeline) will only start producing meaningful text once their engines are wired.

---

## 3. Public API

All public interfaces for the frontend live in `nlg.api`.

### 3.1 `generate`

General entry point for turning a frame into text.

```python
from nlg.api import generate
from nlg.semantics import Frame  # public protocol

def generate(
    lang: str,
    frame: "Frame",
    *,
    options: "GenerationOptions | None" = None,
    debug: bool = False,
) -> "GenerationResult":
    ...
```

**Parameters**

* `lang`: Target language code (e.g. `"en"`, `"fr"`, `"sw"`).
* `frame`: Any supported frame instance (e.g. `PersonFrame` / `BioFrame`, `EventFrame`, membership frame, timeline frame).
* `options`: Optional `GenerationOptions`.
* `debug`: If `True`, debug information is included in the result (when provided by the engine).

**Returns**

* `GenerationResult`

**Example**

```python
from nlg.api import generate, GenerationOptions
from semantics.types import BioFrame, Entity

bio = BioFrame(
    main_entity=Entity(name="Douglas Adams", gender="male", human=True),
    primary_profession_lemmas=["writer"],
)

options = GenerationOptions(
    register="neutral",
    max_sentences=2,
)

result = generate(
    lang="sw",
    frame=bio,
    options=options,
    debug=True,
)

print(result.text)
print(result.debug_info)  # engine, constructions, etc. (if enabled)
```

---

### 3.2 `generate_bio`

Convenience wrapper for biography / person frames.

```python
from nlg.api import generate_bio
from nlg.semantics import BioFrame  # or from semantics.entity.person_frame import PersonFrame

def generate_bio(
    lang: str,
    bio: "BioFrame",
    *,
    options: GenerationOptions | None = None,
    debug: bool = False,
) -> GenerationResult:
    ...
```

Behaves like:

```python
generate(lang=lang, frame=bio, options=options, debug=debug)
```

> **Status:** Fully implemented and backed by the family-specific biography engines via the router (for `frame_type="bio"` frames such as `BioFrame` and `PersonFrame`).

---

### 3.3 `generate_event`

Convenience wrapper for event frames.

```python
from nlg.api import generate_event
from nlg.semantics import EventFrame  # alias of semantics.types.Event

def generate_event(
    lang: str,
    event: "EventFrame",
    *,
    options: GenerationOptions | None = None,
    debug: bool = False,
) -> GenerationResult:
    ...
```

Behaves like:

```python
generate(lang=lang, frame=event, options=options, debug=debug)
```

> **Status:** The function exists and routes through `generate`, but there is currently **no concrete event engine**. Until the event and other non-biography pipelines are implemented, you should expect empty strings / placeholder behavior for those frame families.

As additional frame families become available (e.g. relational frames, timeline frames, narrative / meta frames), more specialized helpers may be added, but the generic `generate` entry point will remain the primary and stable interface.

---

### 3.4 `NLGSession`

Optional stateful interface for long-running processes and services.

```python
from nlg.api import NLGSession
from nlg.semantics import Frame

class NLGSession:
    def __init__(self, *, preload_langs: list[str] | None = None):
        """
        Create a session.

        preload_langs:
            Optional list of language codes to initialize in advance.
        """
        ...

    def generate(
        self,
        lang: str,
        frame: Frame,
        *,
        options: "GenerationOptions | None" = None,
        debug: bool = False,
    ) -> "GenerationResult":
        ...
```

Under the hood, `NLGSession` maintains an internal cache of per-language engines. If the router does not expose a dedicated engine factory for a frame family, it falls back to a small adapter; for now, the only fully wired family is `frame_type="bio"`.

**Usage**

```python
from nlg.api import NLGSession
from semantics.types import BioFrame, Entity

session = NLGSession(preload_langs=["en", "fr"])

bio = BioFrame(
    main_entity=Entity(name="Douglas Adams", gender="male", human=True),
    primary_profession_lemmas=["writer"],
)

result_en = session.generate("en", bio)
result_fr = session.generate("fr", bio)
```

---

## 4. Data models

The concrete semantic types live under the `semantics` package:

* core shared types and legacy frames in `semantics.types`,
* family-specific frames in:

  * `semantics.entity.*`
  * `semantics.event.*`
  * `semantics.relational.*`
  * `semantics.narrative.*`
  * `semantics.meta.*`

Selected core interfaces (`Frame`, `BioFrame`, `EventFrame`) are re-exported from `nlg.semantics` for convenience. The snippets below illustrate the expected shape; for full field inventories, see the `FRAMES_*.md` documents and the JSON schemas under `schemas/frames/`.

### 4.1 Frames

Frames implement a common protocol:

```python
from typing import Protocol

class Frame(Protocol):
    frame_type: str  # canonical values, e.g. "bio", "entity.organization", "event.generic", "rel.membership", "narr.timeline"
```

The `frame_type` string identifies the family and subtype. Engines and routers use this to choose the right family engine and constructions.

Concrete frames are small dataclasses (or equivalent) defined in `semantics.types` and the family modules under `semantics.*`. They are grouped into a finite inventory of frame families.

#### 4.1.1 Frame families (inventory overview)

Conceptually, the final system aims to cover the following families. Each bullet represents one *frame family* and is backed by one or more concrete frame classes and canonical `frame_type` keys (e.g. `"bio"`, `"entity.organization"`, `"event.generic"`, `"rel.definition"`, `"narr.timeline"`, `"meta.article"`).

##### 1. Entity-centric frame families

(Things that are “entities” you can write a lead sentence about.)

1. **Person / biography frame**
   Biographical subjects (real or fictional people). E.g. `BioFrame` / `PersonFrame` (canonical `frame_type="bio"`).

2. **Organization / group frame**
   Companies, NGOs, political parties, sports clubs, bands, research groups.

3. **Geopolitical entity frame**
   Countries, regions, cities, municipalities, dependencies.

4. **Other place / geographic feature frame**
   Mountains, rivers, lakes, seas, islands, national parks, non-political regions.

5. **Facility / infrastructure frame**
   Buildings, bridges, dams, airports, railway stations, power plants, stadiums, monuments.

6. **Astronomical object frame**
   Planets, moons, stars, galaxies, nebulae, minor planets, exoplanets.

7. **Species / taxon frame**
   Species, genera, higher taxa.

8. **Chemical / material frame**
   Elements, compounds, materials.

9. **Physical object / artifact frame**
   Individual artifacts or artifact types (tools, machines, notable objects).

10. **Vehicle / craft frame**
    Ships, aircraft, spacecraft, train classes, car models.

11. **Creative work frame**
    Books, films, TV series, episodes, albums, songs, paintings, games, etc.

12. **Software / website / protocol / standard frame**
    Software packages, websites, internet protocols, standards.

13. **Product / brand frame**
    Commercial product lines and brands.

14. **Sports team / club frame**
    Clubs, franchise teams, national teams.

15. **Competition / tournament / league frame**
    Recurring tournaments, leagues, championship series.

16. **Language frame**
    Natural languages, constructed languages, dialects.

17. **Religion / belief system / ideology frame**
    Religions, denominations, belief systems, political ideologies.

18. **Academic discipline / field / theory frame**
    Academic fields and major theories.

19. **Law / treaty / policy / constitution frame**
    Statutes, treaties, constitutions, major policies.

20. **Project / program / initiative frame**
    Government programs, research projects, campaigns, missions.

21. **Fictional entity / universe / franchise frame**
    Fictional characters, settings, universes, franchises.

##### 2. Event-centric frame families

(Things that happen in time.)

22. **Generic event frame**
    Base event type (participants, roles, time, location, type).

23. **Historical event frame**
    Revolutions, coups, reforms, political transitions.

24. **Conflict / battle / war frame**
    Wars, battles, campaigns, operations.

25. **Election / referendum frame**
    Elections, referendums, leadership contests.

26. **Disaster / accident frame**
    Earthquakes, floods, epidemics, industrial accidents, transport crashes.

27. **Scientific / technical milestone frame**
    Discoveries, inventions, major experiments, firsts.

28. **Cultural event frame**
    Festivals, exhibitions, premieres, ceremonies.

29. **Sports event / match / season frame**
    Individual matches, races, rounds, seasons.

30. **Legal proceeding / case frame**
    Trials, appeals, landmark cases.

31. **Economic / financial event frame**
    Crises, bubbles, crashes, mergers, IPOs, sanctions episodes.

32. **Exploration / expedition / mission frame**
    Expeditions, voyages, space missions.

33. **Life-event subframes (biographical episodes)**
    Education, marriages, appointments, awards, relocations.

##### 3. Relational / statement-level frame families

(Reusable across entity and event articles.)

34. **Definition / classification frame**
    “X is a Y Z” statements.

35. **Attribute / property frame**
    Simple attributes (“X is democratic”, “X is red”).

36. **Quantitative measure frame**
    Numerical values (population, area, GDP, counts, scores).

37. **Comparative / ranking frame**
    Comparisons and rankings (“largest city in…”, “second-highest…”).

38. **Membership / affiliation frame**
    Membership or affiliation in groups (“X is a member of Y”).

39. **Role / position / office frame**
    Office-holding, appointments, terms of office.

40. **Part–whole / composition frame**
    Part–whole and composition relations.

41. **Ownership / control frame**
    Ownership and control relations.

42. **Spatial relation frame**
    Spatial relations (“in”, “near”, “north of”, etc.).

43. **Temporal relation frame**
    Ordering and duration relations between events.

44. **Causal / influence frame**
    Cause / effect and influence relations.

45. **Change-of-state frame**
    Becoming, conversion, abolition, etc.

46. **Communication / statement / quote frame**
    Attributed statements, quotations.

47. **Opinion / evaluation frame**
    Opinions or evaluations with explicit sources (used carefully for NPOV).

48. **Relation-bundle / multi-fact frame**
    Bundles of closely related facts about one subject in one or two sentences.

##### 4. Temporal / narrative / aggregate frame families

49. **Timeline / chronology frame**
    Ordered sequence of key events for a subject.

50. **Career / season / campaign summary frame**
    Summaries of a coherent trajectory (career, season, campaign).

51. **Development / evolution frame**
    How something changes over time (city, product, theory).

52. **Reception / impact frame**
    Critical / public reception and impact.

53. **Structure / organization frame**
    Internal structure of organizations and systems.

54. **Comparison-set / contrast frame**
    Multi-entity comparisons.

55. **List / enumeration frame**
    Enumerations and list-like sentences.

##### 5. Meta / wrapper frame families

56. **Article / document frame**
    Representation of a whole article: subject, sections, ordering.

57. **Section summary frame**
    Summaries of sections (e.g. “Early life”, “Career”, “Legacy”).

58. **Source / citation frame**
    Provenance and citation metadata for other frames.

From the frontend’s point of view, all of these are just `Frame` instances with a `frame_type` string. The engine/router layer decides which concrete family engine to use based on `frame_type`.

#### Example: `BioFrame` / `PersonFrame`

```python
from dataclasses import dataclass, field
from semantics.types import Entity
from nlg.semantics import Frame

@dataclass
class BioFrame(Frame):
    frame_type: str = "bio"
    main_entity: Entity
    primary_profession_lemmas: list[str] = field(default_factory=list)
    nationality_lemmas: list[str] = field(default_factory=list)
    extra: dict | None = None   # optional extra info
```

`PersonFrame` is a thin, explicitly named subclass of `BioFrame` with `frame_type="bio"` registered in `semantics.all_frames`. Either can be passed to `generate_bio` / `generate`.

#### Example: `EventFrame`

```python
from dataclasses import dataclass
from nlg.semantics import Frame

@dataclass
class EventFrame(Frame):
    frame_type: str = "event.generic"
    # Event-specific fields (participants, time, location, etc.)
```

Concrete field sets are defined in the `semantics` package (primarily `semantics.types`, `semantics.normalization`, and the family modules) and should be treated as the source of truth.

---

### 4.2 `GenerationOptions`

High-level configuration for generation.

```python
from dataclasses import dataclass

@dataclass
class GenerationOptions:
    register: str | None = None        # "neutral", "formal", "informal"
    max_sentences: int | None = None   # maximum number of sentences
    discourse_mode: str | None = None  # e.g. "intro", "summary"
    seed: int | None = None            # reserved for future stochastic behavior
```

**Example**

```python
from nlg.api import generate_bio, GenerationOptions

options = GenerationOptions(
    register="neutral",
    max_sentences=1,
)

result = generate_bio("en", bio, options=options)
print(result.text)
```

---

### 4.3 `GenerationResult`

Standard output type for all generation calls.

```python
from dataclasses import dataclass
from typing import Any
from nlg.semantics import Frame

@dataclass
class GenerationResult:
    text: str                          # final realized text
    sentences: list[str]               # sentence-level split
    lang: str                          # language code used
    frame: Frame                       # original frame
    debug_info: dict[str, Any] | None = None
```

**Example**

```python
result = generate_bio("en", bio)

print(result.text)
# "Douglas Adams was a British writer."

print(result.sentences)
# ["Douglas Adams was a British writer."]

print(result.lang)
# "en"
```

If `debug=True` was passed to the generating function, `debug_info` may contain implementation-specific details such as engine identifiers, selected constructions, or intermediate forms (when the underlying engine chooses to expose them).

---

## 5. CLI

A small CLI is provided for quick experiments and linguistic work. It lives in `nlg/cli_frontend.py` and exposes the `nlg-cli` entry point (via packaging).

> **Current limitation:** The CLI only has a fully wired path for `frame_type="bio"`. Other frame types are accepted syntactically but will not yet produce meaningful output until their engines are implemented.

### 5.1 Command: `nlg-cli generate`

General form:

```bash
nlg-cli generate \
  --lang <LANG> \
  --frame-type <FRAME_TYPE> \
  --input <PATH_TO_JSON> \
  [--max-sentences N] \
  [--register neutral|formal|informal] \
  [--discourse-mode MODE] \
  [--debug]
```

**Arguments**

* `--lang`
  Target language code, e.g. `en`, `fr`, `sw`.

* `--frame-type`
  Frame type, e.g. `bio`, `event.generic`, or any other canonical `frame_type` string documented in `docs/FRAMES_*.md`. If omitted, the JSON must contain `frame_type`.

* `--input`
  Path to a JSON file describing the frame. If omitted or `-`, input is read from stdin.

* `--max-sentences` (optional)
  Passed through as `GenerationOptions.max_sentences`.

* `--register` (optional)
  Passed through as `GenerationOptions.register`.

* `--discourse-mode` (optional)
  Passed through as `GenerationOptions.discourse_mode`.

* `--debug` (optional)
  If set, debug information is printed in addition to the main text (when available).

**Example frame JSON (`frame.json`)**

```json
{
  "frame_type": "bio",
  "name": "Douglas Adams",
  "gender": "male",
  "profession_lemma": "writer",
  "nationality_lemma": "British"
}
```

(This is the normalized JSON shape expected by `semantics.normalization.normalize_bio_semantics`, which the CLI uses for `frame_type == "bio"`.)

**Example command**

```bash
nlg-cli generate \
  --lang en \
  --frame-type bio \
  --input frame.json
```

**Output**

* Main text is printed to standard output.
* If `--debug` is provided, additional debug information may be printed or logged.

---

## 6. Integration guidelines

* Use `nlg.api.generate` or `NLGSession.generate` as the only entry points for frontend or service code.
* Construct frames using the models in the `semantics` package (e.g. `BioFrame`, `PersonFrame`, `EventFrame`, and the other frame families described in `docs/FRAMES_*.md`), or via your own JSON → frame conversion based on those types.
* Always set a meaningful `frame_type` string on your frames to identify the frame family; this is how the router selects the appropriate family engine. Canonical strings and their intended semantics are documented in the `FRAMES_*.md` files and enforced by schemas under `schemas/frames/`.
* Prefer `GenerationOptions` to control output style and length; low-level morphological or discourse behavior is handled internally by engines and the router.
* Treat `debug_info` as optional and implementation-specific; do not rely on it for core functionality.
* For now, treat `EventFrame` and all non-biography frame families as **experimental** until their engines are wired. The biography pipeline (`frame_type="bio"`) is the reference implementation.

This frontend API is intentionally thin: it presents a simple, stable surface over a complex multilingual NLG stack while keeping internal modules flexible and evolvable.


