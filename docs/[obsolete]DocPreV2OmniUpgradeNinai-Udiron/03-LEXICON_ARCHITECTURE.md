

# 📚 Lexicon Architecture & Workflow

**Abstract Wiki Architect**

## 1. Core Philosophy: Usage-Based Sharding

Managing vocabulary for 300+ languages is a massive data challenge. A monolithic dictionary file (e.g., `french_all.json`) is inefficient and hard to maintain.

We adopt a **Usage-Based Sharding** strategy:

1. **Upstream Source:** **Wikidata** is the "Raw Material." We use it to trace lineage (QIDs) and fetch translations.
2. **Downstream Usage:** **Domain Shards.** We organize local data by *semantic topic* (People, Science, Core). This allows the engine to load only the vocabulary needed for a specific context (e.g., loading `science.json` only when generating a Physics biography).
3. **Strict Validation:** Every entry must strictly adhere to a JSON schema to ensure the Grammar Engine never crashes due to missing attributes (like `gender`).

---

## 2. Directory Structure

The lexicon lives in `data/lexicon/` and is organized hierarchically by **ISO 639-3** language code.

```text
data/
├── lexicon/
│   ├── schema.json          # Master Validation Schema (Draft-07)
│   ├── eng/                 # English Namespace
│   │   ├── core.json        # "Skeleton" words (is, the, he, she)
│   │   ├── people.json      # Professions, Titles, Relations
│   │   ├── science.json     # Scientific terms (Physics, Nobel Prize)
│   │   └── geography.json   # Countries, Cities, Demonyms
│   ├── fra/                 # French Namespace
│   │   ├── core.json
│   │   └── ...
│   └── zul/                 # Zulu Namespace
│       └── ...
└── imports/                 # Staging area for bulk CSVs
    ├── eng_wide.csv
    └── ...

```

---

## 3. The Semantic Domains

We divide vocabulary into four primary domains. The **Everything Matrix** scanner (`lexicon_scanner.py`) audits these specific files to calculate the "Zone B" readiness score.

### A. `core.json` (The Skeleton)

* **Content:** Functional words required to construct *any* sentence.
* **Examples:** Copulas ("is", "was"), Pronouns ("he", "it"), Articles ("the", "a"), Conjunctions.
* **Criticality:** **Extreme.** If this file is missing or empty, the language is marked as **Broken** (Score 0).

### B. `people.json` (The Biography)

* **Content:** Terms needed for the `BioFrame`.
* **Examples:**
* **Professions:** "Physicist", "Writer", "King".
* **Relations:** "Spouse", "Child", "Advisor".
* **Titles:** "Dr.", "PhD", "Sir".


* **Criticality:** High. Required for the primary use case (Biographies).

### C. `geography.json` (The World)

* **Content:** Location entities and their derived forms.
* **Examples:**
* **Entity:** "France" (Noun).
* **Adjective:** "French" (Adj).
* **Demonym:** "Frenchman" (Noun).


* **Criticality:** Medium. Required for `nationality` fields.

### D. `science.json` (The Domain)

* **Content:** Specialized terminology.
* **Examples:** "Radioactivity", "Planet", "Theory of Relativity".
* **Criticality:** Low (Initial), High (Production).

---

## 4. The Data Schema

Every entry in the JSON files must validate against `data/lexicon/schema.json`.

### Base Entry Object

```json
"physicist": {
  "pos": "NOUN",            // Part of Speech: NOUN, VERB, ADJ, PROPN
  "qid": "Q169470",         // Wikidata ID (Provenance)
  "gender": "m",            // Grammatical Gender (m, f, n, c) - REQUIRED for Romance/Slavic
  "forms": {                // Explicit overrides for irregulars
    "pl": "physicists"
  }
}

```

### Complex Types

**1. Nationalities (`geography.json`)**
Requires linking the country, the adjective, and the person-noun.

```json
"french": {
  "pos": "ADJ",
  "qid": "Q142",            // ID for "France"
  "forms": {
    "m": "français",
    "f": "française",
    "mpl": "français",
    "fpl": "françaises"
  },
  "demonym": {              // Link to the Noun form
    "m": "Français",
    "f": "Française"
  }
}

```

**2. Verbs (`core.json`)**
Requires conjugation stems if the language is not handled by the RGL smart paradigms.

```json
"write": {
  "pos": "VERB",
  "qid": "Q223683",
  "forms": {
    "inf": "write",
    "past": "wrote",
    "pp": "written",
    "pres3sg": "writes"
  }
}

```

---

## 5. Audit & Maturity Scoring (Zone B)

The **Everything Matrix** uses `lexicon_scanner.py` to grade the vocabulary readiness of every language. This score determines if a language is "Data Ready."

| Score | Rating | Requirements |
| --- | --- | --- |
| **0** | 🔴 **Empty** | No JSON files found. |
| **3** | 🟡 **Stub** | Files exist but contain `< 10` words. |
| **5** | 🟠 **Minimal** | `core.json` exists (> 10 words). Can generate "A is B". |
| **8** | 🔵 **Functional** | `core` + `people` exist (> 50 words). Can generate BioFrames. |
| **10** | 🟢 **Production** | All domains present (> 200 words) OR a `_wide.csv` import exists. |

**Impact on Build:**

* If `lex_seed < 3`: The build pipeline marks `data_ready: false`.
* **Auto-Correction:** The **Lexicographer AI** is triggered to generate the missing `core.json`.

---

## 6. Workflows

### Scenario A: Adding a New Language (Bootstrapping)

1. **Create Directory:** `mkdir data/lexicon/zul` (Zulu).
2. **Generate Seed:** Run the Lexicographer agent (or manually create `core.json`).
3. **Audit:** Run `python tools/everything_matrix/build_index.py` to confirm the scanner detects the new files.

### Scenario B: Bulk Import from Wikidata

1. **Fetch:** Use `scripts/fetch_wikidata_labels.py --lang=fr --domain=people`.
2. **Save:** The script outputs `data/imports/fra_wide.csv`.
3. **Audit:** The scanner detects the `.csv` and awards a **Zone B Score of 10**.
4. **Runtime:** The engine lazy-loads the CSV into memory during the first request.

### Scenario C: Fixing a "Missing Word" Error

If the API returns `422 Unprocessable Entity`:

1. **Check Log:** The error message will say `Missing key: 'spaceman' in domain 'people'`.
2. **Edit:** Open `data/lexicon/{lang}/people.json`.
3. **Add:** Insert the entry for "spaceman".
4. **Restart:** You do **not** need to rebuild the PGF. Just restart the Worker/API to flush the JSON cache.