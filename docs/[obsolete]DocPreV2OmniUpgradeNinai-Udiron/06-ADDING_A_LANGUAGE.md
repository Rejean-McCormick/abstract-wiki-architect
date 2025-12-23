
# 🌍 Adding a New Language

**Abstract Wiki Architect**

This guide documents the standard workflow for adding support for a new language (e.g., `por` for Portuguese or `hau` for Hausa) to the Abstract Wiki Architect. The process involves registering the language in the "Everything Matrix", creating its vocabulary, and verifying the build.

---

## 🏗️ Phase 1: Registration (The Matrix)

Before you write any code, you must register the language so the build system knows it exists.

### Step 1: Identify the Tier

Determine which maturity tier your language falls into:

* **Tier 1 (High Road):** Is it supported by the official GF Resource Grammar Library (RGL)? (e.g., Portuguese, Swedish).
* **Tier 3 (Factory):** Is it a new or under-resourced language not in the RGL? (e.g., Zulu, Quechua).

### Step 2: Initialize the Files

Create the necessary directory structure. This physical presence is what the **Matrix Scanners** look for.

**For Tier 1 (RGL-supported):**
Nothing to create here! The `rgl_auditor.py` will automatically detect the language in the `gf-rgl/src` submodule during the next scan.

**For Tier 3 (Factory-generated):**
You must register the language configuration so the Factory can build the "Pidgin" grammar.

1. Open `utils/grammar_factory.py`.
2. Add your language to the `MISSING_LANGUAGES` config:
```python
"hau": {"name": "Hausa", "order": "SVO", "family": "Chadic"}

```



### Step 3: Audit the System

Run the indexer to confirm the system sees your new language.

```bash
python tools/everything_matrix/build_index.py

```

* **Success:** Open `data/indices/everything_matrix.json`. You should see an entry for your new ISO code (e.g., `hau` or `por`).
* **Check:** Verify `build_strategy`.
* Tier 1 should be `"HIGH_ROAD"` (if RGL files are complete).
* Tier 3 should be `"SAFE_MODE"`.



---

## 📚 Phase 2: The Lexicon (The Data)

A grammar without words is useless. You must populate the **Zone B** (Vocabulary) files.

### Step 1: Create the Namespace

Create a folder for your language code in the lexicon directory.

```bash
mkdir -p data/lexicon/por  # For Portuguese

```

### Step 2: Create `core.json` (Mandatory)

This file defines the functional "skeleton" words. Without it, the language is marked as **Broken**.

**File:** `data/lexicon/por/core.json`

```json
{
  "verb_be": {
    "pos": "VERB",
    "lemma": "ser",
    "forms": { "pres_3sg": "é", "past_3sg": "foi" }
  },
  "art_indef_m": { "pos": "ART", "lemma": "um" },
  "art_indef_f": { "pos": "ART", "lemma": "uma" }
}

```

### Step 3: Create `people.json` (Biographical)

Add the terms needed for the standard `BioFrame`.

**File:** `data/lexicon/por/people.json`

```json
{
  "physicist": {
    "pos": "NOUN",
    "gender": "m",
    "qid": "Q169470",
    "forms": { "pl": "físicos", "f": "física" }
  }
}

```

### Step 4: Verify Lexicon Score

Run the indexer again to ensure your **Zone B** score has improved.

```bash
python tools/everything_matrix/build_index.py

```

* **Goal:** `lex_seed` should be .

---

## ⚙️ Phase 3: Configuration (The Logic)

If your language belongs to a supported family (Romance, Germanic, Slavic), you must configure its morphological parameters.

### Step 1: Create the Language Card

**File:** `data/romance/por.json` (Adjust folder based on family)

```json
{
  "meta": { "family": "romance", "code": "por" },
  "articles": {
    "m": { "default": "o", "indef": "um" },
    "f": { "default": "a", "indef": "uma" }
  },
  "morphology": {
    "plural_suffix": "s",
    "gender_default": "m"
  }
}

```

*Note: For Tier 3 "Factory" languages, this step is skipped as the grammar is hardcoded SVO.*

---

## 🚀 Phase 4: Build & Deploy

Now you compile the binary and update the running worker.

### Step 1: Run the Build Orchestrator

This compiles your new language into the PGF binary.

```bash
cd gf
python build_orchestrator.py

```

* **Watch for:** `✅ por: Verified` in Phase 1.
* **Watch for:** `🔗 Linking ...` in Phase 2.

### Step 2: Verify the Binary

Confirm your language is legally inside the binary.

```bash
python3 -c "import pgf; print(pgf.readPGF('AbstractWiki.pgf').languages.keys())"

```

* **Expected Output:** `[..., 'WikiPor', ...]`

### Step 3: Hot-Reload (If running)

If the backend is running, the **Worker** will automatically detect the new `AbstractWiki.pgf` timestamp and reload.

* **Check Logs:** `aw_worker | runtime_detected_file_change ... runtime_reloading_triggered`

---

## 🧪 Phase 5: Smoke Test

Finally, generate a sentence to prove it works end-to-end.

**Request:**

```bash
curl -X POST "http://localhost:8000/api/v1/generate?lang=por" \
     -H "Content-Type: application/json" \
     -d '{
           "frame_type": "bio",
           "name": "Marie Curie",
           "profession": "physicist",
           "nationality": "polish",
           "gender": "f"
         }'

```

**Expected Response:**

```json
{
  "result": "Marie Curie é uma física polonesa.",
  "meta": { "engine": "WikiPor", "strategy": "HIGH_ROAD" }
}

```

---

## 📝 Summary Checklist

| Phase | Action | Verification |
| --- | --- | --- |
| **1. Register** | Create dir (Tier 3) or ensure RGL (Tier 1). | `build_index.py` shows language. |
| **2. Lexicon** | Create `core.json` and `people.json`. | `lex_seed` score . |
| **3. Config** | Add `data/{family}/{lang}.json`. | N/A |
| **4. Build** | Run `build_orchestrator.py`. | Language key in PGF binary. |
| **5. Test** | `curl` request to API. | Valid JSON response. |