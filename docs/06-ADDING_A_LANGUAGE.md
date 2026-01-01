

# 🌍 Adding a New Language

**Abstract Wiki Architect v2.1**

This guide documents the standard workflow for adding support for a new language (e.g., `pt` for Portuguese or `ha` for Hausa) to the Abstract Wiki Architect. The process involves registering the language, bootstrapping data (manually or via AI), and configuring the topology.

---

## 🏗️ Phase 1: Registration (The Matrix)

Before you write any code, you must register the language so the build system knows it exists.

### Step 1: Identify the Tier

Determine which maturity tier your language falls into:

* **Tier 1 (High Road):** Is it supported by the official GF Resource Grammar Library (RGL)? (e.g., Portuguese, Swedish).
* **Tier 3 (Factory):** Is it a new or under-resourced language not in the RGL? (e.g., Zulu, Quechua).

### Step 2: Initialize the Language

**For Tier 1 (RGL-supported):**
Nothing to create here! The `rgl_auditor.py` will automatically detect the language in the `gf-rgl/src` submodule during the next scan.

**For Tier 3 (Factory-generated):**
You must register the language in the "Wishlist" so the **Architect Agent** knows to build it.

1. Open `utils/grammar_factory.py`.
2. Add your language using its **ISO 639-1 (2-letter)** code:

```python
"ha": {"name": "Hausa", "order": "SVO", "family": "Chadic"}


```

*Note: The `order` field ("SVO", "SOV", "VSO") triggers the specific **Weighted Topology** logic.*

### Step 3: Audit the System

Run the indexer to confirm the system sees your new language intention.

```bash
python tools/everything_matrix/build_index.py


```

* **Success:** Open `data/indices/everything_matrix.json`. You should see an entry for your new ISO code (e.g., `ha`).
* **Check:** Verify `build_strategy`.
* Tier 1 should be `"HIGH_ROAD"`.
* Tier 3 should be `"SAFE_MODE"`.

---

## 📚 Phase 2: The Lexicon (The Data)

A grammar without words is useless. You must populate the **Zone B** (Vocabulary) files using the 2-letter directory structure.

### Option A: The AI Shortcut (Recommended)

Use **The Lexicographer** agent to generate the files automatically.

```bash
# Generate core vocabulary (is, the, person)
python -m ai_services.lexicographer --lang=ha --domain=core

# Generate biographical terms (physicist, born, died)
python -m ai_services.lexicographer --lang=ha --domain=people


```

### Option B: Manual Creation

**File:** `data/lexicon/ha/core.json` (Mandatory)

```json
{
  "verb_be": {
    "pos": "VERB",
    "lemma": "ne",
    "forms": { "pres_3sg": "ne", "past_3sg": "ne" }
  }
}


```

**File:** `data/lexicon/ha/people.json`

```json
{
  "physicist": {
    "pos": "NOUN",
    "qid": "Q169470",
    "forms": { "sg": "masanin kimiyyar", "pl": "masana kimiyya" }
  }
}


```

---

## ⚙️ Phase 3: Configuration (Topology)

For Tier 3 languages, the sentence structure is determined by **Weighted Topology Weights** (adapted from Udiron), not hardcoded templates.

### Step 1: Verify Topology Weights

Open `data/config/topology_weights.json`. Ensure the word order you selected in Phase 1 (`SVO`, `SOV`, etc.) exists.

```json
{
  "SVO": { "nsubj": -10, "root": 0, "obj": 10 },
  "SOV": { "nsubj": -10, "obj": -5, "root": 0 }
}


```

*If your language uses a rare order (e.g., OVS for Hixkaryana), add a new entry here.*

---

## 🚀 Phase 4: Build & Deploy

Now you run the build. For Tier 3 languages, this triggers the **Architect Agent**.

### Step 1: Run the Build Orchestrator

```bash
cd gf
python builder/orchestrator.py


```

**What happens for Tier 3?**

1. **Detection:** The system sees `WikiHa` (mapped from `ha`) is missing from `generated/src/`.
2. **Trigger:** `🏗️ Calling The Architect...`
3. **Generation:** The AI writes the grammar using the SVO weights.
4. **Verification:** The compiler runs.
5. **Self-Healing:** If it fails, `🚑 Calling The Surgeon...` patches the code.

### Step 2: Verify the Binary

Confirm your language is legally inside the binary.

```bash
python3 -c "import pgf; print(pgf.readPGF('AbstractWiki.pgf').languages.keys())"


```

* **Expected Output:** `[..., 'WikiHa', ...]`

---

## 🧪 Phase 5: Quality Assurance (The Judge)

Before pushing, you must verify the quality against the Gold Standard.

### Step 1: Add a Gold Standard Test

Open `data/tests/gold_standard.json` and add a verified translation using the 2-letter key.

```json
{
  "lang": "ha",
  "intent": { "frame_type": "bio", "name": "Shaka", "profession": "warrior" },
  "expected": "Shaka jarumi ne."
}


```

### Step 2: Run the Regression Suite

Run the test suite. **The Judge** agent will grade the output.

```bash
python -m pytest tests/integration/test_quality.py --lang=ha


```

* **Pass:** Output matches expected string (Similarity > 0.8).
* **Fail:** The Judge generates a critique and (optionally) opens a GitHub issue.

### Step 3: Smoke Test (API)

Use the correct **Path Parameter** (`/ha`) endpoint.

```bash
curl -X POST "http://localhost:8000/api/v1/generate/ha" \
      -H "Content-Type: application/json" \
      -d '{
            "frame_type": "bio",
            "name": "Shaka",
            "profession": "warrior"
          }'


```

---

## 📝 Summary Checklist

| Phase | Action | Verification |
| --- | --- | --- |
| **1. Register** | Add **ISO-2 code** to `grammar_factory.py`. | `build_index.py` shows language. |
| **2. Lexicon** | Run `lexicographer` with `--lang=xx`. | `lex_seed` score >= 5. |
| **3. Config** | Verify `topology_weights.json`. | N/A |
| **4. Build** | Run `builder/orchestrator.py`. | Language key in PGF binary. |
| **5. QA** | Add to `gold_standard.json` & Run Tests. | Judge Score > 8. |