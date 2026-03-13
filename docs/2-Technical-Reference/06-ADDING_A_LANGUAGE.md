# 🌍 Adding a New Language

**SemantiK Architect v2.5**

This guide documents the standard workflow for adding support for a new language (e.g., `pt` for Portuguese or `ha` for Hausa). The process is:

1. register the language (so it shows up in the Everything Matrix),
2. seed lexicon data,
3. ensure topology config exists (Tier 3),
4. build and confirm the PGF contains the language,
5. add QA coverage.

---

## 🏗️ Phase 1: Registration (The Matrix)

Before you write any grammar code, register the language so the build system knows it exists.

### Step 1: Identify the Tier

* **Tier 1 (High Road):** Supported by GF RGL (Resource Grammar Library) and can be bootstrapped/aligned.
* **Tier 3 (Safe Mode / Factory):** Not in RGL; uses the deterministic Grammar Factory SAFE_MODE output.

### Step 2: Ensure ISO → Wiki suffix mapping is correct

The system uses ISO language codes (usually ISO-639-1 like `pt`, `de`, `ha`) but GF module names use a **Wiki suffix** (e.g., `WikiPor`, `WikiGer`, `WikiEng`). This mapping is authoritative in:

* `data/config/iso_to_wiki.json` (preferred location)

Add/update the entry for your ISO code:

```json
{
  "pt": { "wiki": "Por" },
  "de": { "wiki": "Ger" },
  "ha": { "wiki": "Ha" }
}
```

Notes:

* For **Tier 1** languages, this mapping is usually **required** (RGL suffixes often do *not* match `code.title()`).
* For **Tier 3** languages, if you omit it, the system falls back to `TitleCase` (`ha` → `Ha` → `WikiHa`).

### Step 3: Register Tier 3 languages in the Factory Wishlist (only if Tier 3)

If the language is not in RGL, register it so the system can generate SAFE_MODE grammar:

1. Open `utils/grammar_factory.py`.
2. Add the ISO 2-letter code:

```python
"ha": {"name": "Hausa", "order": "SVO", "family": "Chadic"}
```

The `order` field (`SVO`, `SOV`, `VSO`, …) drives Weighted Topology behavior.

### Step 4: Rebuild the Everything Matrix

Run the indexer so the language appears in the matrix:

```bash
python tools/everything_matrix/build_index.py --langs ha
```

Verify in `data/indices/everything_matrix.json`:

* `verdict.build_strategy` should be:

  * Tier 1: `"HIGH_ROAD"`
  * Tier 3: `"SAFE_MODE"`

---

## 📚 Phase 2: The Lexicon (The Data)

A grammar without words is useless. Populate Zone B lexicon files under the 2-letter directory:

### Manual creation

**File (mandatory):** `data/lexicon/ha/core.json`

```json
{
  "verb_be": {
    "pos": "VERB",
    "lemma": "ne",
    "forms": { "pres_3sg": "ne", "past_3sg": "ne" }
  }
}
```

**File (common):** `data/lexicon/ha/people.json`

```json
{
  "physicist": {
    "pos": "NOUN",
    "qid": "Q169470",
    "forms": { "sg": "masanin kimiyyar", "pl": "masana kimiyya" }
  }
}
```

### Optional: AI-assisted seeding

If enabled in your environment, use the lexicon seeding utility to fill gaps:

```bash
python utils/seed_lexicon_ai.py --langs ha --domains core people --apply
```

---

## ⚙️ Phase 3: Configuration (Topology)

Tier 3 SAFE_MODE grammars use **Weighted Topology**.

1. Open `data/config/topology_weights.json`
2. Ensure your chosen word order exists:

```json
{
  "SVO": { "nsubj": -10, "root": 0, "obj": 10 },
  "SOV": { "nsubj": -10, "obj": -5, "root": 0 }
}
```

If the language uses a rare order, add a new entry.

---

## 🚀 Phase 4: Build & Deploy

### Step 1: Build (preferred entrypoint)

This is the recommended “do the right thing” build entry:

```bash
python manage.py build --langs ha --align
```

* `--langs ha` scopes work to the language you’re adding.
* `--align` performs Tier 1 bootstrap/alignment where applicable, and ensures build inputs are in place.

### Step 2: Orchestrator only (compile + link pipeline)

If you only want the orchestrator step:

```bash
python -m builder.orchestrator --strategy AUTO --langs ha
```

What happens:

* **AUTO** uses `data/indices/everything_matrix.json` verdicts to choose `"HIGH_ROAD"` vs `"SAFE_MODE"` per language.
* Build is **two-phase**: compile individual `.gf` → link into `gf/semantik_architect.pgf`.

### Step 3: Verify the binary contains the language

```bash
python3 -c "import os, pgf; p=os.getenv('PGF_PATH','gf/semantik_architect.pgf'); g=pgf.readPGF(p); print(sorted(g.languages.keys()))"
```

Expected: an entry like `WikiHa` (or `WikiPor`, `WikiGer`, etc. depending on `iso_to_wiki.json`).

---

## 🧪 Phase 5: Quality Assurance (The Judge)

### Step 1: Add a Gold Standard test

Open `data/tests/gold_standard.json` and add:

```json
{
  "lang": "ha",
  "intent": { "frame_type": "bio", "name": "Shaka", "profession": "warrior" },
  "expected": "Shaka jarumi ne."
}
```

### Step 2: Run regression

```bash
python -m pytest tests/integration/test_quality.py --lang=ha
```

### Step 3: Smoke test (API)

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

| Phase           | Action                                                                                              | Verification                                                          |
| --------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| **1. Register** | Add ISO→Wiki mapping in `data/config/iso_to_wiki.json` (and add to `grammar_factory.py` if Tier 3). | `everything_matrix.json` includes language; `build_strategy` correct. |
| **2. Lexicon**  | Create `data/lexicon/<iso2>/*.json` (or seed via `utils/seed_lexicon_ai.py`).                       | Lexicon loads; coverage improves.                                     |
| **3. Config**   | Ensure `topology_weights.json` supports the language’s order (Tier 3).                              | N/A                                                                   |
| **4. Build**    | `python manage.py build --langs xx --align` (or `python -m builder.orchestrator ...`).              | PGF includes `Wiki<Suffix>` language key.                             |
| **5. QA**       | Add gold standard + run tests.                                                                      | Tests pass; output acceptable.                                        |
