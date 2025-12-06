
# NLG Frontend API Documentation

This document describes the public interfaces that frontend integrators (and other callers) use to generate text from semantic frames.

The internals (router, engines, morphology, constructions, discourse, lexicon) remain implementation details and are not required for basic integration.

---

## 1. Overview

The NLG API converts semantic frames into surface text in a target language.

Core concepts:

* `lang`: ISO language code, e.g. `"fr"`, `"sw"`, `"ru"`.
* `Frame`: a semantic object such as `BioFrame` or `EventFrame`.
* `GenerationOptions`: optional settings controlling style and length.
* `GenerationResult`: the structured output containing the final text and metadata.

All examples below assume:

```python
from nlg.api import (
    generate,
    generate_bio,
    generate_event,
    NLGSession,
    GenerationOptions,
    GenerationResult,
)
from nlg.semantics import BioFrame, EventFrame
````

---

## 2. Quick start

Generate text for a biography frame:

```python
bio = BioFrame(
    person={ "qid": "Q42" },
    occupations=[{ "lemma": "writer" }],
    nationalities=[{ "lemma": "British" }],
)

result = generate_bio(lang="en", bio=bio)

print(result.text)       # "Douglas Adams was a British writer."
print(result.sentences)  # ["Douglas Adams was a British writer."]
```

Generate text for a generic frame:

```python
result = generate(lang="fr", frame=bio)
print(result.text)
```

---

## 3. Core API

### 3.1 `generate`

General entry point for “frame → text”.

```python
def generate(
    lang: str,
    frame: "Frame",
    *,
    options: "GenerationOptions | None" = None,
    debug: bool = False,
) -> "GenerationResult":
    ...
```

Parameters:

* `lang`
  ISO 639-1 language code (e.g. `"en"`, `"fr"`, `"sw"`).

* `frame`
  Any semantic frame supported by the system (e.g. `BioFrame`, `EventFrame`).
  Frames are defined in `nlg.semantics`.

* `options` (optional)
  Instance of `GenerationOptions`. See section 4.2.

* `debug` (optional, default `False`)
  If `True`, the returned `GenerationResult` includes implementation-specific debug information.

Return value: `GenerationResult`. See section 4.3.

Usage example:

```python
options = GenerationOptions(max_sentences=2, register="neutral")

result = generate(
    lang="sw",
    frame=bio,
    options=options,
    debug=True,
)

print(result.text)
# result.debug_info may contain engine, constructions, etc.
```

---

### 3.2 `generate_bio`

Specialized helper for biography frames.

```python
def generate_bio(
    lang: str,
    bio: "BioFrame",
    *,
    options: GenerationOptions | None = None,
    debug: bool = False,
) -> GenerationResult:
    ...
```

Behavior:

* Equivalent to calling `generate(lang=lang, frame=bio, options=options, debug=debug)`.
* Provided for convenience and type clarity.

Usage:

```python
result = generate_bio("fr", bio)
print(result.text)
```

---

### 3.3 `generate_event`

Specialized helper for event frames.

```python
def generate_event(
    lang: str,
    event: "EventFrame",
    *,
    options: GenerationOptions | None = None,
    debug: bool = False,
) -> GenerationResult:
    ...
```

Behavior:

* Equivalent to `generate(lang=lang, frame=event, options=options, debug=debug)`.

Usage:

```python
event_frame = EventFrame(
    # event fields here
)

result = generate_event("en", event_frame)
print(result.text)
```

---

## 4. Data models

### 4.1 `Frame` and example frames

All frames implement a common interface:

```python
class Frame(Protocol):
    frame_type: str  # e.g. "bio", "event"
```

Concrete frames live in `nlg.semantics`. Examples:

#### `BioFrame`

```python
@dataclass
class BioFrame(Frame):
    frame_type: str = "bio"
    person: dict                        # e.g. { "qid": "Q42" }
    birth_event: dict | None = None
    death_event: dict | None = None
    occupations: list[dict] = field(default_factory=list)
    nationalities: list[dict] = field(default_factory=list)
    # Additional biography-specific fields as needed
```

#### `EventFrame`

```python
@dataclass
class EventFrame(Frame):
    frame_type: str = "event"
    # Event-specific fields (participants, time, location, etc.)
```

Exact field sets depend on the semantics layer. Callers are expected to construct valid frame objects before calling the NLG API.

---

### 4.2 `GenerationOptions`

Optional controls for generation:

```python
@dataclass
class GenerationOptions:
    register: str | None = None        # "neutral", "formal", "informal"
    max_sentences: int | None = None   # Upper bound on number of sentences
    discourse_mode: str | None = None  # e.g. "intro", "summary"
    seed: int | None = None            # Reserved for future stochastic behavior
```

Typical usage:

```python
options = GenerationOptions(
    register="neutral",
    max_sentences=1,
)

result = generate_bio("en", bio, options=options)
```

---

### 4.3 `GenerationResult`

Standard output from all generation calls:

```python
@dataclass
class GenerationResult:
    text: str                          # Final realized text
    sentences: list[str]               # Optional sentence-level split
    lang: str                          # Language code used
    frame: "Frame"                     # Original frame
    debug_info: dict[str, Any] | None = None
```

Example:

```python
result = generate_bio("en", bio)

result.text
# "Douglas Adams was a British writer."

result.sentences
# ["Douglas Adams was a British writer."]

result.lang
# "en"
```

`debug_info` is implementation-specific and only populated if `debug=True` was passed.

---

## 5. Session API (optional)

For long-running processes or services, use `NLGSession` to reuse loaded resources and avoid repeated initialization.

### 5.1 `NLGSession`

```python
class NLGSession:
    def __init__(self, *, preload_langs: list[str] | None = None):
        """
        Create a session.

        preload_langs:
            Optional list of languages to initialize in advance.
        """
        ...

    def generate(
        self,
        lang: str,
        frame: Frame,
        *,
        options: GenerationOptions | None = None,
        debug: bool = False,
    ) -> GenerationResult:
        ...
```

Usage:

```python
session = NLGSession(preload_langs=["en", "fr"])

bio = BioFrame(
    person={ "qid": "Q42" },
    occupations=[{ "lemma": "writer" }],
)

result_en = session.generate("en", bio)
result_fr = session.generate("fr", bio)

print(result_en.text)
print(result_fr.text)
```

The behavior and return type are identical to the top-level `generate` function; the difference is that `NLGSession` can maintain internal caches.

---

## 6. CLI interface

For quick experiments and linguistic work, a command-line interface is provided.

### 6.1 `nlg-cli generate`

Basic usage:

```bash
nlg-cli generate \
  --lang fr \
  --frame-type bio \
  --input path/to/frame.json \
  --max-sentences 2 \
  --debug
```

Flags:

* `--lang`
  Target language code.

* `--frame-type`
  Type of frame (`bio`, `event`, etc.). Determines how the JSON is parsed.

* `--input`
  Path to a JSON file containing the frame data. If omitted or `-`, input is read from stdin.

* `--max-sentences` (optional)
  Passed through to `GenerationOptions.max_sentences`.

* `--register` (optional)
  Passed through to `GenerationOptions.register` (`neutral`, `formal`, `informal`).

* `--discourse-mode` (optional)
  Passed through to `GenerationOptions.discourse_mode` (e.g. `"intro"`, `"summary"`).

* `--debug` (optional)
  If present, prints debug information in addition to the final text.

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

## 7. Integration guidelines

* Use `nlg.api.generate` or `NLGSession.generate` as the only entry points for frontend or service code.
* Construct frames using the models in the `semantics` / `nlg.semantics` packages (e.g. `BioFrame`, `EventFrame`, and other frame families described in `docs/FRAMES_*.md`), or via your own JSON → frame conversion based on those types.
* Always set a meaningful `frame_type` string on your frames to identify the frame family; this is how the router selects the appropriate family engine. Canonical strings and their intended semantics are documented in the `FRAMES_*.md` files and enforced by schemas under `schemas/frames/`.
* Prefer `GenerationOptions` to control output style and length; low-level morphological or discourse behavior is handled internally by engines and the router.
* Treat `debug_info` as optional and implementation-specific; do not rely on it for core functionality.
* For now, treat `EventFrame` and all non-biography frame families as **experimental** until their engines are wired. The biography pipeline is the reference implementation.

This frontend API is intentionally thin: it presents a simple, stable surface over a complex multilingual NLG stack while keeping internal modules flexible and evolvable.


