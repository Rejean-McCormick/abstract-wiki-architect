
# 🔌 API Reference & Semantic Frames

**SemantiK Architect v2.1**

## 1. Overview

The SemantiK Architect exposes a **Hybrid Natural Language Generation (NLG) Engine** via a RESTful API.
It supports two primary input modes:

1. **Strict Path (BioFrame):** Simple, flat JSON objects validated against a rigid Pydantic schema.
2. **Prototype Path (Ninai/UniversalNode):** Recursive JSON Object Trees for experimental grammar functions.

The engine is **deterministic**: the same input + configuration will always produce the same output, unless "Micro-Planning" (Style Injection) is enabled.

* **Base URL:** `http://localhost:8000/api/v1`
* **Encoding:** UTF-8

---

## 2. Authentication

By default, the API is open for local development (`APP_ENV=development`).

In production, if `API_SECRET` is set in the environment variables, you must include it in the headers.

| Header | Value | Required |
| --- | --- | --- |
| `X-API-Key` | `<Your-API-Secret>` | Yes (Production only) |

---

## 3. Endpoints

### Generate Text

**`POST /api/v1/generate/{lang_code}`**

Generates a natural language sentence from a semantic frame.

**Path Parameters**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `lang_code` | `string` | **Yes** | The **ISO 639-1 (2-letter)** code (e.g., `en`, `fr`, `zu`). **Do NOT use `eng`.** |

**Query Parameters**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `style` | `string` | No | `simple` (default) or `formal`. Triggers Micro-Planning. |

**Headers**

| Header | Value | Description |
| --- | --- | --- |
| `Content-Type` | `application/json` | Required for all requests. |
| `Accept` | `text/plain` | **Default.** Returns a flat string. |
| `Accept` | `text/x-conllu` | **UD Export.** Returns CoNLL-U dependency tags. |
| `X-Session-ID` | `<UUID>` | **Context.** Enables multi-sentence pronominalization. |

---

## 4. Input Mode A: Semantic Frames (Strict Path)

The body must be a **single flat JSON object**. Nested structures (like wrapping the frame in an `intent` object) are deprecated for this endpoint.

### A. Bio Frame (`bio`)

Used for introductory biographical sentences.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `frame_type` | `str` | **Yes** | Must be `"bio"`. |
| `name` | `str` | **Yes** | The subject's proper name (e.g., "Alan Turing"). |
| `profession` | `str` | **Yes** | Lookup key in `people.json` (e.g., "computer_scientist"). |
| `nationality` | `str` | No | Lookup key in `geography.json` (e.g., "british"). |
| `gender` | `str` | No | `"m"`, `"f"`, or `null`. Critical for inflection. |

**Example:**

```json
{
  "frame_type": "bio",
  "name": "Shaka",
  "profession": "warrior",
  "nationality": "zulu",
  "gender": "m"
}

```

### B. Event Frame (`event`)

Used for temporal events.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `frame_type` | `str` | **Yes** | Must be `"event"`. |
| `event_type` | `str` | **Yes** | `"birth"`, `"death"`, `"award"`, `"discovery"`. |
| `subject` | `str` | **Yes** | The entity experiencing the event. |
| `date` | `str` | No | Year or ISO date string. |

---

## 5. Input Mode B: Ninai Protocol (Prototype Path)

The API natively supports the **Ninai JSON Object Model** (or `UniversalNode`) used by Abstract Wikipedia. The recursive structure is automatically flattened by the `NinaiAdapter`.

**Schema:**
The root object must define a `function` key matching the Ninai constructor registry or a valid GF function.

**Example Request:**

```json
{
  "function": "ninai.constructors.Statement",
  "args": [
    { "function": "ninai.types.Bio" },
    { 
      "function": "ninai.constructors.List", 
      "args": ["physicist", "chemist"] 
    },
    { "function": "ninai.constructors.Entity", "args": ["Q42"] }
  ]
}

```

---

## 6. System & Utility Endpoints

### Onboard Language

**`POST /api/v1/languages`**

Scaffolds a new language in the system (Saga Pattern).

**Request Body:**

```json
{
  "iso_code": "it",
  "english_name": "Italian"
}

```

### System Health

**`GET /api/v1/health/ready`**

Returns the status of the Lexicon Store (Zone B) and Grammar Engine (Zone C).

**Response:**

```json
{
  "broker": "up",
  "storage": "up",
  "engine": "up"
}

```

---

## 7. Output Formats

### Standard Text (`Accept: text/plain`)

```json
{
  "surface_text": "Shaka est un guerrier zoulou.",
  "meta": {
    "engine": "WikiFre",
    "strategy": "HighRoad",
    "latency_ms": 12
  }
}

```

### Universal Dependencies (`Accept: text/x-conllu`)

Returns the CoNLL-U representation for evaluation against treebanks.

```json
{
  "surface_text": "# text = Shaka est un guerrier zoulou.\n1 Shaka _ PROPN _ _ 3 nsubj _ _\n...",
  "meta": {
    "exporter": "UDMapping"
  }
}

```

---

## 8. Error Handling

| Status | Error Type | Cause |
| --- | --- | --- |
| **400** | `Bad Request` | Malformed JSON or Schema Validation failed. |
| **404** | `Not Found` | The requested `lang_code` is not in the PGF binary. |
| **422** | `Unprocessable` | A specific word is missing from the Lexicon (`people.json`). |
| **424** | `Failed Dependency` | UD Exporter failed to map a function (check `UD_MAP`). |
| **500** | `Server Error` | Internal engine failure (e.g., C-Runtime crash). |

---

## 9. Integration Guide (Python Client)

```python
import requests
import uuid

# Note the /api/v1 prefix
API_URL = "http://localhost:8000/api/v1/generate"
SESSION_ID = str(uuid.uuid4())

def generate_sentence(frame: dict, lang_code: str = "en") -> str:
    """
    Generates text with context awareness.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Session-ID": SESSION_ID  # Enables 'He/She' logic
    }
    
    # Use Path Parameter for Language
    url = f"{API_URL}/{lang_code}"
    
    response = requests.post(
        url, 
        json=frame, # Flat Dictionary
        headers=headers
    )
    response.raise_for_status()
    return response.json()["surface_text"]

```

```

```