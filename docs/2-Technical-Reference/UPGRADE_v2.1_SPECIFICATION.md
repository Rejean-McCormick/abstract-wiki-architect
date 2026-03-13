# SemantiK Architect: v2.1 Upgrade Specification

**Codename:** "The Brain Transplant"
**Status:** IMPLEMENTED
**Date:** December 23, 2025

## 1. Executive Summary

This upgrade activates **Zone B (Lexicon)**, transforming the Architect from a system that merely passes strings (`"Douglas Adams"`) to a system that understands concepts (`Q42`). It solves the "Cold Start" problem via lazy loading and resolves the "Triangle of Doom" by linking the Abstract Grammar directly to the `gf-wordnet` repository.

**Key Capabilities:**

* **Entity Grounding:** Resolves `QIDs` (Q42) into concrete GF functions (`douglas_adams_PN`) using a harvested dictionary of ~380k words.
* **Semantic Framing:** Replaces generic triples with specific frames (`mkBio`, `mkEvent`).
* **Smart Overloading:** Dynamically selects grammar functions (`mkBioFull` vs `mkBioProf`) based on data availability (P106/P27).

---

## 2. The Data Pipeline (ETL)

We have replaced the manual "Copy-Paste" strategy with an automated **Universal Harvester**.

### Component: The Harvester

* **Path:** `tools/harvest_lexicon.py`
* **Source 1 (The Mine):** Local `gf-wordnet` repo.
* *Logic:* Parses `WordNet.gf` (Abstract) and `WordNet{Lang}.gf` (Concrete) to map `02756049-n`  `apple_N`  `"pomme"`.
* *Robustness:* Implements recursive search to find files hidden in subdirectories (e.g., `gf/bul/WordNetBul.gf`).


* **Source 2 (The Cloud):** Wikidata (SPARQL).
* *Logic:* Fetches labels for generic entities (Names, Cities) missing from WordNet.


* **Output:** Generates `data/lexicon/{lang}/wide.json`.
* *Format:* JSON Shards optimized for O(1) Python lookup.



---

## 3. The Runtime Architecture (Python)

The "Brain" of the system has been rewired to hold the massive lexicon in memory without crashing the worker.

### A. The Memory Bank (`app/shared/lexicon.py`)

* **Role:** Singleton In-Memory Database.
* **Mechanism:** **Lazy Loading**. It does not load all 77 languages at startup. It loads a language's `wide.json` shard (50MB+) only when a request for that language arrives.
* **Lookup Strategy:**
1. **Primary:** QID Match (`Q42`  `douglas_adams_PN`).
2. **Fallback:** Lemma Match (`"Douglas Adams"`  `douglas_adams_PN`).



### B. The Bridge (`app/adapters/ninai.py`)

* **Role:** Converts Ninai JSON  GF Abstract Syntax Tree.
* **Upgrade:** Integrated `LexiconRuntime`.
* **Logic Flow:**
1. Receive `{"function": "mkBio", "args": ["Q42", "Q123"]}`.
2. Ask Lexicon: "What is Q42 in Russian?"  Returns `douglas_adams_PN`.
3. Ask Lexicon: "What is Q123 in Russian?"  Returns `edinburgh_PN`.
4. Generate Tree: `mkBio (douglas_adams_PN) (edinburgh_PN)`.


* **Safety:** If a QID is missing from the lexicon, it degrades gracefully to a String Literal: `mkBio (mkPN "Douglas Adams") ...`.

### C. The Worker (`app/workers/worker.py`)

* **Startup Routine:**
1. Loads `Wiki.pgf` (Zone A Grammar).
2. **Pre-loads** `eng` Lexicon (Zone B) to ensure zero latency for the default language.


* **Zombie Filter:** Checks `everything_matrix.json` before loading a language. If `verdict.runnable` is `False`, the language is purged from the runtime to prevent user-facing errors.

---

## 4. The Grammar Architecture (GF)

We have established the **"Triangle of Doom"** alignment between the Schema (Abstract) and the Vocabulary (Concrete).

### A. The Schema (`gf/semantik_architect.gf`)

Defines the strict API contract. To handle real-world data variance, we use **Overloading**:

```haskell
cat Statement ; Entity ; Profession ; Nationality ;
fun
  -- The "Perfect" Case (P106 + P27 exist)
  mkBioFull : Entity -> Profession -> Nationality -> Statement ;
  
  -- The "Partial" Cases (Missing Data)
  mkBioProf : Entity -> Profession -> Statement ;
  mkBioNat  : Entity -> Nationality -> Statement ;
  
  -- Type Coercion (Allows WordNet functions to fit our Schema)
  lexProf : N -> Profession ; 
  lexNat  : A -> Nationality ;

```

### B. The Implementation (`gf/WikiEng.gf`)

The Concrete Grammar must now **open** the external WordNet module to access the 380k identifiers.

```haskell
concrete WikiEng of SemantikArchitect = open SyntaxEng, ParadigmsEng, WordNetEng in {
  -- 'open WordNetEng' allows us to use 'physicist_N' directly
  lin
    mkBioFull s p n = mkS (mkCl s (mkVP n p)) ; -- "He is an American physicist"
    mkBioProf s p   = mkS (mkCl s (mkVP (mkCN p))) ; -- "He is a physicist"
    
    -- Coercion
    lexProf n = mkCN n ;
}

```

---

## 5. Execution Guide

To deploy v2.1, execute the following sequence in **WSL**.

### Phase 1: Harvest (Zone B)

```bash
# 1. Harvest local WordNet data (The "Rosetta Stone")
python3 tools/harvest_lexicon.py wordnet \
  --root "/mnt/c/MyCode/SemantiK_Architect/gf-wordnet" \
  --langs eng,rus,bul,swe

# 2. Update the Everything Matrix
python3 tools/everything_matrix/build_index.py

```

### Phase 2: Compile (Zone A)

```bash
# 1. Define the Schema (with Overloading)
echo 'abstract SemantikArchitect = { flags startcat = Statement ; cat Statement ; Entity ; Profession ; Nationality ; fun mkEntity : PN -> Entity ; mkBioFull : Entity -> Profession -> Nationality -> Statement ; mkBioProf : Entity -> Profession -> Statement ; lexProf : N -> Profession ; lexNat : N -> Nationality ; }' > gf/semantik_architect.gf

# 2. Define the Concrete (linking WordNet)
echo 'concrete WikiEng of SemantikArchitect = open SyntaxEng, ParadigmsEng, WordNetEng in { lincat Statement = S ; Entity = NP ; Profession = CN ; Nationality = AP ; lin mkEntity pn = mkNP pn ; mkBioFull s p n = mkS (mkCl s (mkVP n p)) ; mkBioProf s p = mkS (mkCl s (mkVP p)) ; lexProf n = mkCN n ; lexNat n = mkAP (mkA n) ; }' > gf/WikiEng.gf

# 3. Build the PGF (This links everything together)
# Note: Use -path to point to the WordNet repo
gf -make -output-format=pgf -path ".:/mnt/c/MyCode/SemantiK_Architect/gf-wordnet/gf" gf/WikiEng.gf

```

### Phase 3: Run

```bash
# Start the API Worker
python3 -m uvicorn app.main:app --reload

```

---

## 6. Known Limitations & Next Steps

1. **Memory Footprint:** Loading `wide.json` into Python RAM is temporary. For v3.0, migrate to **Redis** or **SQLite**.
2. **Morphology Gaps:** If `WordNet` provides a Noun (`american_N`) but we need an Adjective (`mkBioNat`), the current grammar attempts coercion. This may fail for languages with complex morphology (e.g., Russian).
* *Fix:* Future versions of `NinaiAdapter` should check `pos` tag in `wide.json`.


3. **Fact Harvesting:** Currently, we only harvest *Lexicon* (Words). We need a separate `harvest_facts.py` to fetch P106/P27 claims from Wikidata to populate the `mkBio` arguments automatically.
