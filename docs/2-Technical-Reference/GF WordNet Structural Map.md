
# 🗺️ GF WordNet Structural Map (v1.0)

**Target Repository:** `gf-wordnet`
**Purpose:** Lexicon Harvesting & Data Injection for SemantiK Architect.

## 1. The Core Architecture (The "Rosetta Stone")

The repository is built on a **Star Topology**. The `WordNet` module is the center, and all 30+ languages are spokes that implement it.

| Component | File Pattern | Role | Key Characteristic |
| --- | --- | --- | --- |
| **Abstract Interface** | `gf/WordNet.gf` | **Primary Key Database** | Defines function names (`apple_N`) and maps them to WordNet IDs (`02756049-n`). |
| **Concrete Lexicon** | `gf/WordNet{Lang}.gf` | **Value Store** | Contains the actual words. E.g., `lin apple_N = mkN "pomme"`. |
| **Assembler** | `Parse{Lang}.gf` | **Compiler Entry** | Binds the Lexicon (`WordNetFre`) to the Grammar (`ParseExtendFre`). |
| **Extension** | `ParseExtend{Lang}.gf` | **Grammar Patch** | Adds extra grammatical rules (e.g., `CompVP`, `InOrderToVP`) not found in standard RGL. |

---

## 2. Directory Structure & Key Files

Based on the file scan, here is the functional breakdown of the directory tree:

### 📂 Root / `gf/`

* **`WordNet.gf`**: **CRITICAL.** The source of truth for semantic IDs.
* *Format:* `fun function_name : Cat ; -- SynsetID`.


* **`WordNet{Lang}.gf`** (e.g., `WordNetRus.gf`): **CRITICAL.** The target for harvesting.
* *Format:* `lin function_name = constructor "word" ;`.


* **`Parse.gf`**: The Abstract Grammar definition that enforces the `WordNet` dependency.
* **`Parse{Lang}.gf`** (e.g., `ParseEng.gf`): The top-level concrete grammar. Useful for testing but **not** for harvesting words directly.

### 📂 `bootstrap/`

* Contains Haskell scripts (`bootstrap.hs`, `build.hs`) used to generate the initial GF files from the Princeton WordNet database.
* *Relevance:* Low for harvesting, High for understanding provenance.

### 📂 `morphodicts/`

* **`MorphoDict{Lang}.gf`**: Contains raw inflection tables for complex languages (Arabic, etc.).
* *Relevance:* **High.** If the harvester sees `variants {}` in `WordNet{Lang}.gf`, the word might be hidden here or missing.

### 📂 `www/` & `www-services/`

* Web interface code for the Cloud GF WordNet browser.
* *Relevance:* None for the build pipeline.

---

## 3. The Data Linking Protocol

To extract a usable dictionary (`JSON Shard`), the harvester must traverse this specific path:

### Step 1: Extract the Semantic Key (Abstract)

**Source:** `gf/WordNet.gf`
**Regex:** `fun\s+(\w+)\s*:\s*\w+\s*;\s*--\s*([Q\d]+-?[a-z]*)`
**Example Match:**

* Function: `a_bomb_N`
* ID: `02756049-n`

### Step 2: Extract the Lexical Value (Concrete)

**Source:** `gf/WordNet{Lang}.gf`
**Regex:** `lin\s+(\w+)\s*=\s*(.*?)\s*;`
**Example Match (Rus):**

* Function: `a_bomb_N`
* RHS: `compoundN (mkA "атомный" "1*a") (mkN "бомба" feminine inanimate "1a")`
* **Extracted Lemma:** "атомный", "бомба" (Heuristic: grab string literals).

### Step 3: Semantic Alignment (Wikidata)

The `WordNet.gf` file contains two types of IDs in the comments:

1. **WordNet IDs:** `02756049-n` (8 digits + pos tag).
2. **Wikidata QIDs:** `Q25287` (e.g., `fun gothenburg_1_LN : LN ; -- Q25287`).

**Action:** The harvester must detect `Q` prefixes and save them to the `qid` field in the JSON output. This enables the **"Q42 Killer"** logic in the Architect.

---

## 4. Known "Gotchas" & Edge Cases

1. **`variants {}`**:
* Many definitions in `WordNetRus.gf` use `variants {}`.
* *Meaning:* The word is **missing** in that language.
* *Action:* The harvester must skip these entries to avoid polluting the database with empty strings.


2. **`--guessed`**:
* Comments like `--guessed` appear frequently in `WordNetRus.gf`.
* *Meaning:* AI or heuristic generation, not manually verified.
* *Action:* Flag these in the JSON with `status: "guessed"` for lower confidence scores.


3. **Compound Nouns**:
* Code: `compoundN (mkN "costume") "zoot"`
* *Challenge:* The lemma is split across multiple strings.
* *Action:* Concatenate string literals or take the head noun (first argument) depending on harvester sophistication.