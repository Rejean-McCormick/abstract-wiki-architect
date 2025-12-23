# 🔌 API Reference & Semantic Frames

**Abstract Wiki Architect**

## 1. Overview

The Abstract Wiki Architect exposes a **Rule-Based Natural Language Generation (NLG) Engine** via a RESTful API. Unlike LLMs, this API is **deterministic**: the same input (Semantic Frame) + the same configuration (Grammar/Lexicon) will *always* produce the exact same output.

* **Base URL:** `http://localhost:8000/api/v1`
* **Content-Type:** `application/json`
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

**`POST /generate`**

Converts an abstract Semantic Frame into a natural language sentence in the target language.

**Query Parameters**

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `lang` | `string` | **Yes** | The 3-letter ISO 639-3 code (e.g., `eng`, `fra`, `zul`). |

**Request Body**

The body must be a single **Semantic Frame** object. The schema validation is strict; extra fields are ignored, but missing required fields will trigger a `400 Bad Request`.

**Example Request (cURL)**

```bash
curl -X POST "http://localhost:8000/api/v1/generate?lang=fra" \
     -H "Content-Type: application/json" \
     -d '{
           "frame_type": "bio",
           "name": "Marie Curie",
           "profession": "physicist",
           "nationality": "polish",
           "gender": "f"
         }'

```

---

## 4. Semantic Frame Schemas

The system uses a "Frame-Based" approach. The `frame_type` field determines which linguistic template is triggered.

### A. Bio Frame (`bio`)

Used for introductory biographical sentences (the "Lead Sentence" of a Wikipedia article). It handles complex morphology like gender agreement for professions and nationalities.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `frame_type` | `str` | **Yes** | Must be `"bio"`. |
| `name` | `str` | **Yes** | The subject's proper name (e.g., "Alan Turing"). |
| `profession` | `str` | **Yes** | Lookup key in `people.json`. Must match a valid entry (e.g., "computer_scientist"). |
| `nationality` | `str` | No | Lookup key in `geography.json` (e.g., "british", "american"). |
| `gender` | `str` | No | `"m"`, `"f"`, or `"n"`. Critical for Romance/Slavic languages to inflect the profession correctly. |

**JSON Example:**

```json
{
  "frame_type": "bio",
  "name": "Shaka",
  "profession": "warrior",
  "nationality": "zulu",
  "gender": "m"
}

```

### B. Relational Frame (`relational`)

Used to express a direct relationship between two entities (Subject-Predicate-Object).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `frame_type` | `str` | **Yes** | Must be `"relational"`. |
| `subject` | `str` | **Yes** | The agent/subject (e.g., "Pierre Curie"). |
| `relation` | `str` | **Yes** | Predicate key from `people.json` (e.g., "spouse_of", "advisor_to"). |
| `object` | `str` | **Yes** | The patient/target (e.g., "Marie Curie"). |

**JSON Example:**

```json
{
  "frame_type": "relational",
  "subject": "Pierre Curie",
  "relation": "spouse_of",
  "object": "Marie Curie"
}

```

### C. Event Frame (`event`)

Used for temporal events. This triggers specific tense logic (Past/Present).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `frame_type` | `str` | **Yes** | Must be `"event"`. |
| `event_type` | `str` | **Yes** | `"birth"`, `"death"`, `"award"`, `"discovery"`. |
| `subject` | `str` | **Yes** | The entity experiencing the event. |
| `date` | `str` | No | Year or ISO date string (e.g., "1934"). |
| `location` | `str` | No | Lookup key in `geography.json` (e.g., "Paris"). |

**JSON Example:**

```json
{
  "frame_type": "event",
  "event_type": "birth",
  "subject": "Albert Einstein",
  "date": "1879",
  "location": "germany"
}

```

---

## 5. Response Format

### Success (200 OK)

Returns the generated text and engine metadata.

```json
{
  "result": "Shaka est un guerrier zoulou.",
  "meta": {
    "lang": "fra",
    "engine": "WikiFra",          // The concrete grammar used
    "strategy": "HIGH_ROAD",      // Tier 1 (RGL) or Tier 3 (Factory)
    "latency_ms": 12
  }
}

```

### Error Handling

| Status | Error Type | Cause |
| --- | --- | --- |
| **400** | `Bad Request` | JSON body is malformed or missing `frame_type`. |
| **404** | `Not Found` | The requested `lang` is not in the `AbstractWiki.pgf` binary. (Check the **Everything Matrix**). |
| **422** | `Unprocessable` | A specific word (e.g., "spaceman") is missing from the Lexicon (`people.json`). The error message will specify the missing key. |
| **500** | `Server Error` | Internal engine failure (e.g., C-runtime crash, missing PGF file). |

---

## 6. Integration Guide (Python)

Below is a robust client function to consume the API.

```python
import requests
from typing import Optional

API_URL = "http://localhost:8000/api/v1/generate"

def generate_bio(
    name: str, 
    profession: str, 
    nationality: str, 
    lang: str = "eng", 
    gender: Optional[str] = None
) -> str:
    """
    Generates a biographical sentence using the Architect API.
    """
    payload = {
        "frame_type": "bio",
        "name": name,
        "profession": profession,
        "nationality": nationality
    }
    
    if gender:
        payload["gender"] = gender

    try:
        response = requests.post(
            API_URL, 
            params={"lang": lang}, 
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        
        data = response.json()
        return data["result"]
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            print(f"❌ Lexicon Missing: {e.response.text}")
        elif e.response.status_code == 404:
            print(f"❌ Language '{lang}' not supported.")
        else:
            print(f"❌ API Error: {e}")
        return f"{name} ({profession})"  # Fallback

```