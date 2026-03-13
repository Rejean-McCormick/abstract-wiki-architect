Here is the final, **Exhaustive v2.0 Variable & Configuration Ledger**.

I have added **Section 10 (Topology Weights)** and **Section 11 (Gold Standard Paths)** to capture the Udiron-derived configurations that were missing from the previous draft. This document is now fully aligned with the v2.0 Architecture Spec.

You should save this as **`docs/14-VAR_FIX_LEDGER.md`**.

---

### 🔐 v2.0 Variable & Configuration Ledger (Exhaustive)

**SemantiK Architect**

#### 1. Purpose

This document "freezes" all variable names, database keys, and protocol strings for the v2.0 Omni-Upgrade. **All code implementations must copy-paste these values exactly.** Do not invent new variable names or logic paths.

---

#### 2. Environment Variables (`.env`)

These must be defined in `app/shared/config.py` using Pydantic `BaseSettings`.

| Variable Name | Type | Default / Example Value | Description |
| --- | --- | --- | --- |
| **`APP_ENV`** | `str` | `"development"` | Toggles debug mode (`development`, `staging`, `production`). |
| **`LOG_LEVEL`** | `str` | `"INFO"` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| **`REDIS_URL`** | `str` | `"redis://redis:6379/0"` | Connection string for Session Store (Discourse Context). |
| **`SESSION_TTL_SEC`** | `int` | `600` | Expiration time for Discourse Context keys (10 mins). |
| **`GITHUB_TOKEN`** | `str` | `""` | PAT (Personal Access Token) for the Judge Agent (QA). |
| **`REPO_URL`** | `str` | `"https://github.com/my-org/awa"` | Target repository URL for QA Issue creation. |
| **`AI_MODEL_NAME`** | `str` | `"gemini-1.5-pro"` | The specific LLM model version for Architect & Judge agents. |
| **`GOOGLE_API_KEY`** | `str` | `""` | API Key for Google Gemini services. |
| **`GF_LIB_PATH`** | `str` | `"/app/gf-rgl"` | Absolute path to the RGL source inside the container. |
| **`PGF_PATH`** | `str` | `"/app/gf/semantik_architect.pgf"` | Path to the compiled binary grammar file. |

---

#### 3. Redis Schema

**Namespace:** `awa:`

| Key Pattern | Data Structure | TTL | Description |
| --- | --- | --- | --- |
| **`awa:session:{session_id}`** | `JSON String` | `SESSION_TTL_SEC` | Stores the `SessionContext` object for pronominalization. |
| **`awa:lock:build`** | `String` | `60s` | Mutex lock for the Architect Agent to prevent concurrent builds. |
| **`awa:cache:lexicon:{lang}`** | `JSON String` | `3600s` | Caches heavy lexicon files to avoid disk I/O on every request. |

**JSON Payload (`SessionContext`):**

```json
{
  "session_id": "uuid-v4",
  "history_depth": 0,
  "current_focus": {
    "label": "Marie Curie",
    "gender": "f",
    "qid": "Q7186",
    "recency": 1
  }
}

```

---

#### 4. Ninai Protocol Constants (JSON/Object)

The `NinaiAdapter` must parse JSON object structures, not LISP strings. The keys below map strictly to the `ninai` Python API and internal logic.

| Constant Name | Value / Key | Description |
| --- | --- | --- |
| **`KEY_FUNC`** | `"function"` | JSON key identifying the constructor class name. |
| **`KEY_ARGS`** | `"args"` | JSON key containing the list of arguments for the constructor. |
| **`CLS_LIST`** | `"ninai.constructors.List"` | Identifies a Ninai List object (trigger for recursive flattening). |
| **`CLS_STATEMENT`** | `"ninai.constructors.Statement"` | Identifies a declarative sentence payload. |
| **`CLS_SUPPORT`** | `"ninai.constructors.Support"` | Identifies reference/metadata wrappers (ignored or stripped). |
| **`CLS_ENTITY`** | `"ninai.constructors.Entity"` | Wrapper for QIDs (e.g., `args=["Q42"]`). |
| **`CLS_TYPE_BIO`** | `"ninai.types.Bio"` | Maps to `frame_type="bio"`. |
| **`CLS_TYPE_EVENT`** | `"ninai.types.Event"` | Maps to `frame_type="event"`. |

---

#### 5. Universal Dependencies (UD) Truth Table

This dictionary **MUST** be implemented exactly in `app/core/exporters/ud_mapping.py`. It defines the rigid mapping between RGL functions and UD tags.

```python
# FROZEN DICTIONARY
UD_MAP = {
    # Clause Level
    "mkCl":  {"arg1": "nsubj", "arg2": "root", "arg3": "obj"},
    "mkS":   {"arg1": "root"},
    "mkUtt": {"arg1": "root"},
    "mkQS":  {"arg1": "root"},  # Question Sentence

    # Noun Phrase Level
    "mkNP":  {"arg1": "det", "arg2": "head"},
    "mkCN":  {"arg1": "amod", "arg2": "head"},
    "UseN":  {"arg1": "head"},
    "AdvNP": {"arg1": "head", "arg2": "nmod"},
    "DetCN": {"arg1": "det", "arg2": "head"},

    # Verb Phrase Level
    "mkVP":  {"arg1": "head", "arg2": "obj"},  # Basic V + O
    "AdvVP": {"arg1": "head", "arg2": "advmod"},

    # Fallback
    "DEFAULT": "dep"
}

```

---

#### 6. AI System Prompts (Frozen Strings)

The "Architect Agent" must use this **exact** system prompt in `ai_services/prompts.py` to guarantee deterministic, code-only output.

**Constant Name:** `ARCHITECT_SYSTEM_PROMPT`

> "You are the SemantiK Architect, an expert in Grammatical Framework (GF). Your task is to write a Concrete Grammar file (*.gf) for a specific language.
> **CRITICAL RULES:**
> 1. Output **ONLY** the raw GF code.
> 2. **NO** Markdown code blocks (```).
> 3. **NO** conversational filler ('Here is the code...').
> 4. Implement the 'SemantikArchitect' interface exactly.
> 5. Use standard RGL modules: `Syntax`, `Paradigms`."
> 
> 

---

#### 7. Interactive QA Payload

The JSON payload sent by the Judge Agent to the GitHub API.

**Endpoint:** `POST /repos/{owner}/{repo}/issues`

| Field | Value Template |
| --- | --- |
| **`title`** | `"[QA] Poor Quality: {lang} - {frame_type}"` |
| **`labels`** | `["linguistics", "auto-generated", "v2-audit"]` |
| **`body`** | See template below. |

**Body Template:**

```markdown
### 🚨 Linguistic Quality Alert

**Language:** {lang}
**Frame:** {frame_type}
**Confidence:** {confidence_score}

**Generated Output:**
> "{generated_text}"

**Critique:**
{judge_critique}

**Metadata:**
* Engine: {engine_name}
* Strategy: {strategy} (Tier 1/3)
* Session ID: {session_id}

*Reported by SKA Judge Agent*

```

---

#### 8. Pydantic Model Fields (Domain Objects)

To avoid `KeyError` exceptions, these class definitions in `app/core/domain/` are final.

### `DiscourseEntity` (Class)

* `label`: `str` (The surface text, e.g., "Marie Curie")
* `gender`: `str` (Must be one of: `"m", "f", "n", "c"`)
* `qid`: `str` (Must match regex `^Q\d+$`, e.g., "Q42")
* `recency`: `int` (0 for current, incremented each turn)

### `SessionContext` (Class)

* `session_id`: `str` (UUID4)
* `history_depth`: `int` (Default 0)
* `current_focus`: `Optional[DiscourseEntity]` (The entity currently in focus for pronominalization)

### `BioFrame` (Update for v2.0)

* `frame_type`: `Literal["bio"]`
* `name`: `str`
* `profession`: `str` (Can be comma-separated list)
* `nationality`: `Optional[str]`
* `gender`: `Optional[Literal["m", "f", "n"]]`
* `context_id`: `Optional[str]` (New field for session linking)

---

#### 9. Error Codes (v2.0 Extension)

These map to specific HTTP Status Codes and internal Exception classes.

| HTTP Code | Exception Class | Description |
| --- | --- | --- |
| **400** | `NinaiParseError` | Malformed JSON or invalid constructor key in input payload. |
| **400** | `FrameValidationError` | Input frame missing required fields (e.g., `name` in BioFrame). |
| **404** | `LanguageNotFoundError` | The requested language ISO code is not in the PGF binary. |
| **409** | `SessionConflict` | Concurrent write to same Redis session key (Optimistic Locking failure). |
| **422** | `LexiconMissingError` | A required word (e.g., profession) is missing from `people.json`. |
| **424** | `RGLMappingError` | UD Exporter encountered an unmapped RGL function and `DEFAULT` fallback failed. |
| **503** | `AgentQuotaExceeded` | The Architect Agent hit the Gemini/OpenAI API rate limit. |
| **500** | `GFRuntimeError` | The C-runtime for PGF crashed or returned null. |

---

#### 10. Topology Weights Schema (Udiron Integration)

Used by `utils/grammar_factory.py` to order dependencies for Tier 3 languages.
**File:** `data/config/topology_weights.json`

```json
{
  "SVO": { "nsubj": -10, "root": 0, "obj": 10 },
  "SOV": { "nsubj": -10, "obj": -5, "root": 0 },
  "VSO": { "root": -10, "nsubj": 0, "obj": 10 },
  "VOS": { "root": -10, "obj": 5, "nsubj": 10 },
  "OVS": { "obj": -10, "root": 0, "nsubj": 10 },
  "OSV": { "obj": -10, "nsubj": -5, "root": 0 }
}

```

---

#### 11. Gold Standard Paths

Paths to the validation datasets ingested from Udiron.

| Key | Path | Description |
| --- | --- | --- |
| **`GOLD_TESTS_PATH`** | `data/tests/gold_standard.json` | The `tests.json` file migrated from Udiron. |
| **`GOLD_SCHEMA_PATH`** | `data/tests/schema.json` | Validation schema for test cases. |
