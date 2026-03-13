Here is the **Exhaustive v2.0 "Omni-Upgrade" Architecture Specification**.

This document is the definitive technical blueprint for the upgrade. It expands on every logic flow, data structure, and integration point derived from the `Ninai` and `Udiron` code audits. You should replace the contents of `docs/13-V2_ARCHITECTURE_SPEC.md` with this version.

---

# 🏗️ v2.0 "Omni-Upgrade" Architecture Specification (Exhaustive)

**SemantiK Architect**

## 1. Executive Summary

This specification defines the "v2.0" architectural expansion. The goal is to evolve the system from a **Sentence-Level Rule-Based Engine** into a **Context-Aware, Interoperable, and AI-Augmented Platform**.

**The 7 Core Pillars of Upgrade:**

1. **Interoperability:** Ninai Bridge (JSON Object Adapter).
2. **Standards:** UD Exporter (CoNLL-U Tag Mapping).
3. **Linguistics:** Discourse Planner (Context & Pronominalization).
4. **Automation:** The "Architect" Agent (Generative Grammar Creation).
5. **DevOps:** Interactive QA (Auto-Ticketing & Gold Standard Validation).
6. **Core Optimization:** Weighted Topology Factory (Udiron-style Linearization).
7. **Hybridization:** Learned Micro-Planning (Style Injection).

---

## 2. Component A: The Ninai Bridge (Input Adapter)

**Role:** Transforms the Architect into a native renderer for Abstract Wikipedia by accepting `Ninai` JSON Object structures directly.

### 2.1 The Translation Logic

Unlike the v1.0 regex approach, v2.0 uses a **Recursive Object Walker**. It treats the input as a Python/JSON tree, respecting the specific constructor keys found in the `Ninai` codebase.

* **Location:** `app/adapters/ninai.py`
* **Input Schema (Ninai JSON):**
```json
{
  "function": "ninai.constructors.Statement",
  "args": [
    { "function": "ninai.types.Bio" },
    { "function": "ninai.constructors.List", "args": [
        { "function": "ninai.constructors.Entity", "args": ["Q1"] },
        { "function": "ninai.constructors.Entity", "args": ["Q2"] }
    ]}
  ]
}

```



### 2.2 Extraction Strategy

The adapter traverses the JSON tree and applies specific transformation rules based on the `function` key:

| Ninai Constructor Key | Target SKA Field | Logic |
| --- | --- | --- |
| `ninai.types.Bio` | `frame_type` | Static mapping  `"bio"`. |
| `ninai.types.Event` | `frame_type` | Static mapping  `"event"`. |
| `ninai.constructors.List` | `N/A` (Intermediate) | **Recursive Flatten:** Calls `_walk()` on all items in `args[]`, joins results with `", "`. |
| `ninai.constructors.Entity` | `subject` / `object` | Extracts the QID string (e.g., `"Q42"`) from `args[0]`. |
| `ninai.constructors.Statement` | `N/A` (Root) | Maps `args[0]` to type, `args[1]` to subject, etc. |

### 2.3 Data Flow

1. **Ingest:** `POST /generate` detects `Content-Type: application/json` + `X-Format: ninai`.
2. **Parse:** `NinaiAdapter.parse(payload)` initiates the recursive walk.
3. **Map:** Converts the extracted QIDs and strings into a `BioFrame` or `EventFrame` object.
4. **Validate:** Runs strict Pydantic validation (e.g., ensuring `profession` is present for Bio frames).

---

## 3. Component B: The UD Exporter (Output Adapter)

**Role:** Enables evaluation against Universal Dependencies (UD) treebanks by converting internal GF trees into the industry-standard CoNLL-U format.

### 3.1 The "Construction-Time Tagging" Strategy

Since we generate text constructively (GF) rather than parsing it (UD), we map the **intent** of the RGL functions to UD tags.

* **Location:** `app/core/exporters/ud_mapping.py`
* **Frozen Mapping Table:**
```python
UD_MAP = {
    "mkCl":  {"arg1": "nsubj", "arg2": "root", "arg3": "obj"}, # Subject, Verb, Object
    "mkS":   {"arg1": "root"},                                 # Sentence Root
    "mkNP":  {"arg1": "det", "arg2": "head"},                  # Det + Noun
    "mkCN":  {"arg1": "amod", "arg2": "head"},                 # Adj + Noun
    "UseN":  {"arg1": "head"},                                 # Bare Noun
    "AdvNP": {"arg1": "head", "arg2": "nmod"}                 # Noun + Modifier
}

```



### 3.2 Output Format

The API supports `Accept: text/x-conllu`. The output mimics a dependency parse:

```text
# text = Marie Curie est une physicienne.
# source = SemantikArchitect v2.0 (WikiFre)
1   Marie     Marie     PROPN   _   _   2   nsubj   _   _
2   Curie     Curie     PROPN   _   _   3   nsubj   _   _
3   est       être      VERB    _   _   0   root    _   _

```

---

## 4. Component C: The Discourse Planner (Context)

**Role:** Introduces statefulness to the API. It manages a "Session Context" in Redis to handle multi-sentence coherence (e.g., replacing names with pronouns).

### 4.1 Storage Schema

We implement a dedicated Pydantic model for the Redis payload.

* **Location:** `app/core/domain/context.py`
* **Key:** `awa:session:{uuid}` (TTL: 600s)
* **Payload (`SessionContext`):**
```json
{
  "session_id": "a1b2-c3d4",
  "history_depth": 1,
  "current_focus": {
    "label": "Marie Curie",
    "gender": "f",
    "qid": "Q7186",
    "recency": 0
  }
}

```



### 4.2 The Pronominalization Logic

1. **Check:** Middleware intercepts the request. Is `X-Session-ID` present?
2. **Fetch:** Retrieve `SessionContext` from Redis.
3. **Compare:** Does `frame.subject_qid` == `context.current_focus.qid`?
4. **Mutate:**
* **If Match:** Change `frame.subject` to `"She"` (or language-specific pronoun).
* **If Mismatch:** Keep name, update `current_focus` to the new subject.


5. **Save:** Write updated context back to Redis.

---

## 5. Component D: The "Architect" Agent (Automation)

**Role:** Completely automates the creation of Tier 3 grammars. It replaces the "Pidgin" templates with AI-generated GF code, validated by the compiler.

### 5.1 The "Architect" Workflow

This logic runs inside `builder/orchestrator.py`.

1. **Detection:** Scanner identifies a missing language (e.g., `WikiHau.gf`).
2. **Prompting:** Sends the **Frozen System Prompt** (see Ledger) to Gemini/LLM.
* *Prompt Context:* "Write a Concrete Grammar for Hausa (SVO). Use `mkS`, `mkCl`, `mkNP`."


3. **Drafting:** Saves the LLM output to `generated/src/WikiHau.gf`.
4. **Verification:** Runs `gf -batch -c WikiHau.gf`.
5. **Repair Loop ("The Surgeon"):**
* If compilation fails, feed the error log back to the LLM: "You used `mkN` but Hausa requires `mkN0`. Fix it."
* Max Retries: 3.



---

## 6. Component E: Interactive QA (DevOps)

**Role:** Closes the quality loop by validating output against "Gold Standard" data and auto-filing bug reports.

### 6.1 Gold Standard Integration

We ingest the **Udiron Test Suite** as ground truth.

* **Source:** `data/tests/gold_standard.json` (Migrated from Udiron).
* **Logic:** The Judge Agent runs a daily regression test:
* *Input:* `tests.json` Intent.
* *Output:* SKA Generation.
* *Metric:* Levenshtein Distance & Semantic Similarity.



### 6.2 The "Whistleblower" (Auto-Ticketing)

If a Tier 1 (High Road) language fails a Gold Standard test:

1. **Trigger:** `similarity_score < 0.8`.
2. **Payload:** Constructs a GitHub Issue Markdown body.
3. **Action:** `POST /repos/{org}/{repo}/issues` using `GITHUB_TOKEN`.
* *Title:* `[QA] Regression: {Language} - {FrameType}`.
* *Body:* "Expected 'X', got 'Y'. Confidence: Low."



---

## 7. Component F: Shared Configuration (Infrastructure)

**Role:** Centralizes all v2.0 environment variables to prevent configuration drift.

### 7.1 Settings Update (`config.py`)

```python
class Settings(BaseSettings):
    # Core
    APP_ENV: str = "development"
    GF_LIB_PATH: str = "/app/gf-rgl"

    # v2.0 Architecture
    REDIS_URL: str = "redis://redis:6379/0"
    SESSION_TTL_SEC: int = 600

    # DevOps / QA
    GITHUB_TOKEN: Optional[str] = None
    REPO_URL: str = "https://github.com/org/repo"
    AI_MODEL_NAME: str = "gemini-1.5-pro"

```

---

## 8. Component G: Weighted Topology Factory (Tier 3 Upgrade)

**Role:** Adapts **Udiron's Linearization Logic** to solve the "Word Order Problem" for generated grammars.

### 8.1 The Problem

The current Factory hardcodes `SVO` (`subj ++ verb ++ obj`). This produces grammatically incorrect output for languages like Japanese (SOV) or Irish (VSO).

### 8.2 The Solution: Topology Weights

We introduce a configuration file that defines relative positions for syntactic roles.

* **Location:** `data/config/topology_weights.json`
* **Schema:**
```json
{
  "SVO": { "nsubj": -10, "root": 0, "obj": 10 },
  "SOV": { "nsubj": -10, "obj": -5, "root": 0 },
  "VSO": { "root": -10, "nsubj": 0, "obj": 10 }
}

```



### 8.3 Integration Logic

In `utils/grammar_factory.py`, the generation logic is refactored:

1. **Lookup:** Check `MISSING_LANGUAGES[lang]['order']` (e.g., "SOV").
2. **Assign:** Retrieve weights: `subj (-10)`, `obj (-5)`, `verb (0)`.
3. **Sort:** Order the components by weight.
4. **Generate:** Emit the GF `lin` rule in the correct sorted order:
* `lin S = mkS (subj ++ obj ++ verb);`



---

## 9. Component H: Learned Micro-Planning (Hybridization)

**Role:** Injects stylistic variation using a lightweight AI call *before* the rigorous GF rendering.

### 9.1 The Logic

1. **Input:** API receives `style="formal"`.
2. **Intercept:** `MicroPlanner` passes the frame to LLM: "Rewrite this BioFrame to be formal. Change 'died' to 'passed away'."
3. **Render:** The *modified* frame is passed to the GF engine.
4. **Result:** Grammatically perfect text (GF) with stylistically varied vocabulary (AI).

---

## 10. Implementation Roadmap

To execute this "Omni-Upgrade" without breaking the build, follow this strict order:

1. **Phase 1: Foundation**
* Update `config.py` (Pydantic settings).
* Create `data/config/topology_weights.json`.


2. **Phase 2: Adapters (Deterministic)**
* Implement `NinaiAdapter` (Recursive JSON).
* Implement `UDMapping` (Table-based).


3. **Phase 3: Core Logic (Optimization)**
* Upgrade `grammar_factory.py` with Weighted Topology.
* Implement `SessionContext` & Redis hooks.


4. **Phase 4: AI Services (Probabilistic)**
* Create `prompts.py` (Frozen Prompts).
* Upgrade `Judge` with Gold Standard data & GitHub Client.


5. **Phase 5: Integration**
* Wire middleware into `api.py`.
* Deploy `builder/orchestrator.py` with the Architect Agent.
