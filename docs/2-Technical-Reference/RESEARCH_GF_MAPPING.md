
# GF Integration Design

Status: draft  
Owner: (TBD)  
Scope: integrate selected parts of **Grammatical Framework (GF)** into **SemantiK Architect (SKA)** without changing SKA’s core architecture.

---

## 1. Goals and Non-Goals

### 1.1 Goals

1. **Leverage GF’s linguistic work** without adopting GF as the core platform:
   - Reuse GF’s **morphology paradigms** (RGL) to strengthen SKA’s morphology configs.
   - Borrow **syntactic patterns** and **test cases** to improve constructions and QA.

2. **Keep SKA’s architecture intact**:
   - Still use **family engines + JSON configs + lexicon subsystem + frames**.
   - No dependency on GF in the runtime generation pipeline.

3. **Make integration repeatable and auditable**:
   - Clear tooling to re-import/refresh GF-derived resources.
   - All GF-derived data carries provenance metadata (version, module, language).

4. **Stay license-clean and modular**:
   - GF is BSD-style; we must preserve attribution.
   - GF integration must be optional and clearly separated in the repo.

### 1.2 Non-Goals

- Do **not**:
  - Port GF’s compiler or AST model into SKA.
  - Make SKA dependent on GF for runtime generation.
  - Implement parsing or reversible grammars.
  - Port full GF concrete syntaxes per language.

- We only use GF as:
  - an **offline source of paradigms, rule patterns, and test cases**, and
  - conceptual inspiration for constructions.

---

## 2. Scope Overview

The integration is split into three phases (loosely independent):

1. **Phase 1 – Morphology integration (high priority)**  
   Toolchain to import GF’s noun/adj/verb paradigms into SKA’s JSON morphology configs and/or language cards.

2. **Phase 2 – Syntax pattern harvesting (medium priority)**  
   Human-guided extraction of word order and construction patterns from RGL; ported into SKA constructions and family engines.

3. **Phase 3 – Test case integration (medium priority)**  
   Use GF grammars to generate contrastive test pairs for morphology and syntax; import them as CSV rows into SKA’s QA suites.

---

## 3. Current SKA Architecture (Short Recap)

Core elements relevant for integration:

- `engines/` – **family engines** orchestrating:
  - morphology (`morphology/<family>.py`),
  - constructions (`constructions/...`),
  - lexicon (`lexicon/...`).

- `data/morphology_configs/` – **family grammar matrices**:
  - e.g. `romance_grammar_matrix.json`, `slavic_matrix.json`.
  - Capture family-level paradigms, morphological category space, default rules.

- `data/<family>/<lang>.json` – **language cards**:
  - overrides and language-specific morphological parameters.

- `data/lexicon/*.json` – lexica:
  - `lemma`, `pos`, features (gender, number, etc.), IDs.

- QA pipeline:
  - `qa_tools/test_suite_generator.py` → CSV templates.
  - `qa/test_runner.py` → SKA generation vs expected outputs.
  - `qa_tools/lexicon_coverage_report.py` → lexicon coverage.

GF integration will feed into:

- `data/morphology_configs/*`  
- `data/<family>/*`  
- `qa_tools/generated_datasets/*` (test CSVs)

Nothing in the runtime core (router, engines, constructions) should require GF at runtime.

---

## 4. GF Overview (Only What We Use)

- GF provides:
  - **Resource Grammar Library (RGL)**:
    - per-language morphology and syntax modules,
    - lexical categories, inflection paradigms, function signatures.

- Relevant pieces for us:
  1. **Morphology paradigms** (inflection tables, rules).
  2. **Syntactic constructors** (clause building, phrase building).
  3. **Regression tests** and examples used to validate RGL.

We will treat GF as an **offline tool** installed locally (or in CI) for generation of intermediate artifacts.

---

## 5. High-Level Integration Architecture

### 5.1 Components

1. **GF Export Layer** (external dependency, optional)
   - Small GF scripts or commands to dump:
     - paradigm tables (lemma → forms),
     - sample sentences for constructions.

2. **Conversion Layer (`gf_integration/`)** (new in SKA)
   - Python utilities to transform GF exports into:
     - SKA morphology JSON (grammar matrix + language cards),
     - SKA QA CSV rows,
     - optional helper JSON/YAML for syntactic patterns.

3. **Consumption Layer** (existing SKA code)
   - SKA family engines and morphology modules continue to read:
     - `data/morphology_configs/*`,
     - `data/<family>/*.json`,
     - `qa_tools/generated_datasets/*.csv`.

### 5.2 Data Flow (Morphology)

```text
GF RGL .gf files
     │
     ├─[gf export scripts]───────────────►  gf_morph_export.json  (intermediate)
     │
     └─[gf_integration/convert_morphology.py]►
             data/morphology_configs/<family>_gf_enriched.json
             data/<family>/<lang>_gf_card.json
````

### 5.3 Data Flow (QA Tests)

```text
GF grammars + test ASTs
     │
     ├─[gf export tests]─────────────────►  gf_test_sentences.csv
     │
     └─[gf_integration/convert_tests.py]─►
             qa_tools/generated_datasets/test_suite_<lang>_gf.csv
```

### 5.4 Isolation

* All GF-dependent scripts live under:

  * `gf_integration/` and/or `tools/gf/`.
* Generated artifacts are:

  * committed to `data/*` and `qa_tools/generated_datasets/*` as plain JSON/CSV.
* Runtime never calls GF; it only reads JSON/CSV.

---

## 6. Phase 1 – Morphology Integration

### 6.1 Target: morphology configs and language cards

We want to:

* enrich `data/morphology_configs/<family>_grammar_matrix.json` with:

  * more complete paradigms,
  * better irregular rules,
  * more accurate stem/affix patterns;
* optionally create/extend `data/<family>/<lang>.json` from GF data.

### 6.2 Source: GF morphology

For each language `L`:

* GF RGL module typically has:

  * categories like `N`, `A`, `V`, `Adv`, `Det`,
  * inflection functions like:

    * `mkN` (noun paradigm),
    * `mkA` (adjective paradigm),
    * `mkV` (verb paradigm),
    * plus irregular entries.

* We treat these as describing:

  * paradigm type,
  * inflection slots (e.g. `Mas Sg`, `Fem Pl`, person/tense endings),
  * phonological adjustments.

### 6.3 Intermediate model

Define an intermediate JSON schema, e.g. `gf_morph_export.json`:

```json
{
  "language": "it",
  "gf_version": "3.12",
  "paradigms": [
    {
      "category": "N",
      "name": "Noun_o_a",
      "slots": ["Masc_Sg", "Fem_Sg", "Masc_Pl", "Fem_Pl"],
      "examples": [
        {
          "lemma": "amico",
          "forms": {
            "Masc_Sg": "amico",
            "Fem_Sg": "amica",
            "Masc_Pl": "amici",
            "Fem_Pl": "amiche"
          }
        }
      ],
      "rules": {
        "stem_pattern": ".*o",
        "transformations": [
          { "from": "o", "to": "a", "slot": "Fem_Sg" },
          { "from": "o", "to": "i", "slot": "Masc_Pl" },
          { "from": "co", "to": "che", "slot": "Fem_Pl", "condition": "..."}
        ]
      }
    }
  ]
}
```

The exact structure can be adapted, but we need:

* category,
* slot inventory,
* transformation rules,
* at least one exemplar per paradigm.

This file is produced by GF export scripts (outside SKA Python).

### 6.4 Conversion to SKA grammar matrices

Create `gf_integration/convert_morphology.py`:

Responsibilities:

1. **Read intermediate export** (`gf_morph_export.json`).
2. **Map GF categories and slots to SKA categories and features**:

   * e.g. `category="N"` → SKA `pos="NOUN"`.
   * `slot="Masc_Sg"` → `{"gender": "masc", "number": "sg"}`.
3. **Inject/merge into SKA family matrix**:

   * open `data/morphology_configs/romance_grammar_matrix.json`,
   * update or extend:

     * paradigm definitions,
     * suffix rules,
     * phonological rules.
4. **Emit enriched config files**:

   * either overwrite the existing matrix, or
   * generate `*_gf_enriched.json` and then manually promote.

#### 6.4.1 Mapping table (sketch)

Create a static mapping in `gf_integration/mappings.py`:

```python
GF_POS_TO_SKA = {
    "N": "NOUN",
    "A": "ADJ",
    "V": "VERB",
    "Adv": "ADV",
    # ...
}

GF_SLOT_TO_FEATURES = {
    "Masc_Sg": {"gender": "masc", "number": "sg"},
    "Fem_Sg":  {"gender": "fem",  "number": "sg"},
    "Masc_Pl": {"gender": "masc", "number": "pl"},
    "Fem_Pl":  {"gender": "fem",  "number": "pl"},
    # ...
}
```

These mappings are family-specific and may be extended as we add more languages.

### 6.5 Language cards

Where GF provides language-specific quirks that should not live in the shared family matrix (e.g. special elision, clitic binding, orthographic niceties), we record them in:

* `data/<family>/<lang>_gf_card.json` or merge into existing `data/<family>/<lang>.json`.

Example fields:

```json
{
  "language": "it",
  "source": "gf-rgl-3.12",
  "article_elision": [
    { "before_vowel": true, "article": "lo", "elided": "l'" }
  ],
  "special_clusters": [
    { "pattern": "s + consonant", "article": "uno" }
  ]
}
```

### 6.6 Integration with existing morphology code

After generating the enriched configs:

1. Update `morphology/<family>.py` to:

   * recognise new paradigm IDs,
   * apply the newly imported transformations.

2. Add regression tests in `qa/test_*.py`:

   * for languages where GF data is integrated,
   * verifying a few paradigms end-to-end.

3. Update `docs/LEXICON_ARCHITECTURE.md` and `docs/LEXICON_WORKFLOW.md`:

   * note that some paradigms are GF-derived,
   * specify refresh steps.

### 6.7 Versioning and provenance

Every GF-derived file must include provenance in its `meta`:

```json
{
  "_meta": {
    "source": "gf-rgl",
    "gf_version": "3.12",
    "gf_modules": ["Italian/Noun.gf", "Italian/Adjective.gf"],
    "generated_at": "2025-12-06T12:00:00Z"
  },
  "paradigms": [ ... ]
}
```

---

## 7. Phase 2 – Syntax Pattern Harvesting

This phase is more manual and conceptual than Phase 1.

### 7.1 Objective

Use GF’s syntactic design to refine SKA’s:

* constructions (word order, phrase structure),
* family engine logic (clitics, argument order, topicalisation).

We **do not** import GF syntax code directly. Instead, we:

* inspect GF modules (RGL `Syntax`, `Paradigms`, `Sentence`),
* translate key patterns into SKA constructions.

### 7.2 Workflow

1. **Identify focus constructions** in SKA:

   * simple copula (`copula_equative_simple`, `copula_equative_classification`),
   * basic clauses (`intransitive_event`, `transitive_event`),
   * relative clauses (`relative_clause_subject_gap`),
   * coordination, comparatives, existentials.

2. For each construction:

   * review corresponding GF RGL functions (e.g. `mkCl`, `mkS`, `mkRS`, etc.) for several languages,
   * document word-order rules and parameterization:

     * SVO vs SOV,
     * adjective position (pre/post),
     * negation particles, clitics.

3. Amend SKA constructions:

   * add configuration hooks in `constructions/base.py` for:

     * clause skeleton templates,
     * slot reordering (subject, verb, object, adverbials),
     * optional positions for topic markers or clitics.
   * set defaults per family/language in `language_profiles/profiles.json` and/or family matrices.

4. Add examples to docs:

   * for each major pattern, include a brief note in `docs/FRAMES_NARRATIVE.md` or separate `docs/SYNTAX_NOTES.md`.

### 7.3 Deliverables

* `docs/GF_SYNTAX_NOTES_<family>.md`:

  * summary of imported GF insights per language family.
* Adjusted constructions and engines:

  * more accurate word order,
  * more consistent cross-language parameterisation.

---

## 8. Phase 3 – Test Case Integration

### 8.1 Objective

Use GF’s grammars as a **test oracle** to generate:

* contrastive examples for morphology (correct vs wrong forms),
* syntactic minimal pairs (e.g. clitic placement, agreement).

These become rows in SKA’s CSV test suites.

### 8.2 Data Flow

```text
GF test grammars / examples
     │
     ├─[gf generate tests]────────────►  gf_test_sentences.csv
     │      (lang, phenomenon, input parameters, output_strings[])
     │
     └─[gf_integration/convert_tests.py]►
             qa_tools/generated_datasets/test_suite_<lang>_gf.csv
```

Example intermediate CSV:

```csv
lang,phenomenon,input,good,bad1,bad2
it,adj_agreement,"Adj=grande,N=ragazzo", "il grande ragazzo","il grande ragazza","i grande ragazzo"
```

`convert_tests.py` then:

* maps each row to one or more SKA test rows:

  * build the corresponding `BioFrame` or other frame,
  * place `good` as `EXPECTED_OUTPUT`,
  * optionally use `badX` as negative examples or comments.

### 8.3 Integration with QA

* `qa_tools/test_suite_generator.py`:

  * extended to optionally include GF-derived tests when generating new CSVs.
* `qa/test_runner.py`:

  * treat GF-derived test suites the same as human-authored ones.
* Optionally, dedicated GF-specific suites:

  * `test_suite_<lang>_gf_morph.csv`,
  * `test_suite_<lang>_gf_syntax.csv`.

Provenance columns:

* `SOURCE=gf_rgl`,
* `GF_VERSION`,
* `GF_MODULE`.

---

## 9. Repo Layout Changes

Proposed additions:

```text
abstract-wiki-architect/
  gf_integration/
    __init__.py
    mappings.py
    convert_morphology.py
    convert_tests.py
    README.md           # how to install GF, run exporters, etc.

  tools/gf/             # optional
    export_morphology.gf
    export_tests.gf

  docs/
    GF_INTEGRATION.md   # this document
    GF_SYNTAX_NOTES_romance.md
    GF_SYNTAX_NOTES_slavic.md
    ...
```

---

## 10. Implementation Plan

### Milestone 1 – Skeleton and one language (Romance: Italian)

1. Add `gf_integration/` skeleton and mappings.
2. Write minimal GF exporter:

   * `tools/gf/export_morphology.gf` for Italian.
3. Generate `gf_morph_export_it.json`.
4. Implement `convert_morphology.py` → update `romance_grammar_matrix.json` and `data/romance/it.json`.
5. Extend `morphology/romance.py` to use new paradigms.
6. Add a small GF-based test suite for Italian morphology.
7. Verify tests; update docs.

### Milestone 2 – Additional languages in same family

1. Repeat for Spanish, French, Portuguese, Romanian.
2. Consolidate mappings for Romance.
3. Add shared `GF_SYNTAX_NOTES_romance.md` and adjust constructions as needed.

### Milestone 3 – Another family (Slavic, Germanic, etc.)

Repeat Milestone 1–2 pattern per family.

### Milestone 4 – Test integration

1. Implement `export_tests.gf` for at least one language.
2. Generate test CSV and integrate via `convert_tests.py`.
3. Wire into QA generator/runner.
4. Document process in `docs/GF_INTEGRATION.md`.

---

## 11. Risks and Mitigations

### 11.1 Risk: mismatch between GF and SKA feature sets

* GF may have richer morphological categories or slightly different category splits.
* Mitigation:

  * design explicit mappings in `gf_integration/mappings.py`,
  * allow partial import (ignore unused categories),
  * add validation to flag unmapped slots.

### 11.2 Risk: overfitting to GF assumptions

* GF grammars reflect specific theoretical choices that may not align with AW needs.
* Mitigation:

  * GF is used as **one source**, not authoritative truth,
  * manual review of paradigm and pattern imports per language.

### 11.3 Risk: maintenance burden

* GF may evolve; re-importing paradigms might break configs.
* Mitigation:

  * capture GF version in meta,
  * treat imports as semi-manual: run scripts, inspect diffs, then commit,
  * do not auto-refresh GF imports in CI without human review.

---

## 12. Licensing and Attribution

* GF is BSD-licensed; include:

  * a pointer to GF’s LICENSE in `docs/GF_INTEGRATION.md`,
  * explicit note in generated files’ `_meta.source` fields.

Example meta snippet:

```json
{
  "_meta": {
    "source": "GF Resource Grammar Library",
    "license": "BSD-style",
    "url": "https://www.grammaticalframework.org/",
    "gf_version": "3.12"
  }
}
```

---

## 13. Summary

* We **do not** adopt GF’s architecture.

* We **do** import:

  * morphology paradigms,
  * syntactic insights,
  * test cases.

* Runtime remains:

  * frames → discourse → constructions → family engines → SKA morphology + lexicon.

GF becomes an **offline knowledge provider** for richer paradigms and tests, under clear versioning and provenance.

This design keeps SemantiK Architect aligned with Abstract Wikipedia/Wikifunctions needs while leveraging decades of grammar-engineering work in GF.

