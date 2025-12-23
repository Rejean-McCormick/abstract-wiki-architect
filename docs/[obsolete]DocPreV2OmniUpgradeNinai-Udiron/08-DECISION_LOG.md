

# 📜 Decision Log & Architecture Records

**Abstract Wiki Architect**

This document records the **key architectural choices** behind the Abstract Wiki Architect and the alternatives that were considered. It is meant to be a concise "Why we did it this way" reference for reviewers and future contributors.

---

## 1. Overall System Shape

### Decision: Router  Family Engine  Constructions  Morphology  Lexicon

**The Context**
NLG systems can be built as monoliths (hardcoded strings) or as pipelines. We needed a structure that could handle 300+ languages without 300x code duplication.

**The Decision**
We adopted a **Hexagonal, Pipeline-based Architecture**:

1. **Router:** Selects the correct engine based on the language request.
2. **Constructions:** Selects the sentence pattern (e.g., "Equative Clause").
3. **Family Engine:** Applies broad typological rules (e.g., "Romance Adjective Agreement").
4. **Morphology:** Handles specific inflection (e.g., "French plural 's' vs 'x'").
5. **Lexicon:** Injects the raw vocabulary.

**Why we chose this**

* **Reuse:** Family engines allow us to write the logic for "Adjective Agreement" once for the entire Romance family (French, Spanish, Italian, Portuguese) rather than 4 times.
* **Modularity:** Lexicon changes do not break grammar rules.

---

## 2. Family Engines Instead of Language-Specific Engines

### Decision: ~15 Family Engines (Romance, Germanic, Bantu...)

**The Context**
We considered writing a `FrenchEngine`, `EnglishEngine`, `ZuluEngine`, etc.

**The Decision**
We implemented **Family-Level Engines** (e.g., `RomanceEngine`) that read configuration files for specific languages.

**Why we chose this**

* **Typology:** Languages within a family share 80-90% of their structural logic.
* **Maintenance:** Fixing a bug in the `RomanceEngine` fixes it for 5+ languages simultaneously.
* **Scale:** Managing 15 files is feasible; managing 300 is not.

---

## 3. The "Everything Matrix" (Data-Driven Build)

### Decision: Dynamic System Scanning instead of Static Config

**The Context**
Initially, we hardcoded the list of supported languages (`LANGS = [...]`). As the number of languages grew, this became unmanageable and prone to "drift" (config saying a language exists when it doesn't).

**The Decision**
We built the **Everything Matrix** (`data/indices/everything_matrix.json`), a dynamic registry populated by scanning the filesystem before every build.

**Why we chose this**

* **Truth:** The build system never lies. If the file isn't on disk, the Matrix marks the language as `BROKEN` or `MISSING`.


* 
**Automation:** Adding a new language is as simple as adding the files; the scanner detects and registers it automatically.



---

## 4. The "Two-Phase" Build Pipeline

### Decision: Verify-then-Link (Solving "Last Man Standing")

**The Context**
We discovered a critical bug in the Grammatical Framework (GF) compiler: running `gf -make` in a loop overwrites the binary, meaning the final `.pgf` file only contained the last language processed.

**The Decision**
We implemented a strict **Two-Phase Build**:

1. 
**Phase 1 (Verify):** Run `gf -c -batch` for each language to generate intermediate object files (`.gfo`) and verify correctness.


2. 
**Phase 2 (Link):** Run a *single* `gf -make` command containing *all* valid languages to link them into one binary.



**Why we chose this**

* 
**Correctness:** It is the only way to produce a multi-lingual PGF binary.


* 
**Resilience:** If one language fails verification, it is excluded from the final Link command, preventing the entire build from crashing.



---

## 5. Usage-Based Lexicon Sharding

### Decision: Domain Shards (`core.json`, `people.json`) vs. Monolith

**The Context**
Loading a massive dictionary into memory for every request is slow and wasteful. Most requests only need specific words.

**The Decision**
We split the lexicon into semantic domains:

* `core.json`: Functional words (always loaded).
* `people.json`: Biographical terms (loaded for `BioFrame`).
* `science.json`: Scientific terms (loaded on demand).

**Why we chose this**

* **Performance:** Reduced memory footprint and faster startup times.
* **Organization:** Easier for humans (and AI agents) to manage smaller, focused files.

---

## 6. Hybrid Factory Architecture

### Decision: "Pidgin" Fallback for Missing Languages

**The Context**
The official GF Resource Grammar Library (RGL) only covers ~40 languages. We need 300+. Manual implementation of the remaining 260 is impossible with current resources.

**The Decision**
We adopted a **Tiered System**:

* **Tier 1 (High Road):** Use RGL where available.
* **Tier 3 (Factory):** Auto-generate simplified "Pidgin" (SVO) grammars for the rest to ensure 100% API coverage.

**Why we chose this**

* **Availability:** Better to have a simplified output ("Shaka is warrior") than a 404 Error.
* **Evolution:** We can incrementally upgrade a Tier 3 language to Tier 1 without changing the API contract.

---

## 7. AI Services Integration

### Decision: "Surgeon" and "Judge" Agents

**The Context**
Rule-based systems are brittle. A single missing semicolon breaks the build. A missing word crashes the renderer.

**The Decision**
We integrated **Gemini-powered Agents**:

* **The Surgeon:** Reads compiler logs and patches broken code.
* **The Lexicographer:** Generates missing vocabulary entries.

**Why we chose this**

* **Resilience:** The system can "Self-Heal" minor errors, reducing developer intervention.
* **Speed:** AI can generate boilerplate lexicon files much faster than humans.

---

## 8. Summary

The key design choices are:

1. 
**Hexagonal Architecture** for code modularity.


2. **Family Engines** for linguistic efficiency.
3. 
**Data-Driven Build (The Matrix)** for reliability.


4. 
**Two-Phase Compilation** to solve the PGF linking bug.


5. **Sharded Lexicons** for performance.
6. **Hybrid Factory** for 100% language coverage.

Together, these choices create a system that is **scalable, robust, and autonomous**.