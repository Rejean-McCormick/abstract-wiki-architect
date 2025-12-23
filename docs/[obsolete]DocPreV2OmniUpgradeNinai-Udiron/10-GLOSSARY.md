# 📖 Project Glossary & Terminology

**Abstract Wiki Architect**

This document defines the specialized terminology used across the project. It bridges the gap between **Software Engineering** concepts and **Computational Linguistics** concepts.

---

## 🏛️ System Architecture Terms

### **Everything Matrix**
* **Definition:** The dynamic registry (`everything_matrix.json`) that tracks the maturity and build status of every language in the system.
* **Context:** It replaces static configuration. The system scans the filesystem to populate this matrix.
* **Code:** `tools/everything_matrix/`

### **Hexagonal Architecture**
* **Definition:** A design pattern (Ports & Adapters) that isolates the core domain logic from external tools like databases or APIs.
* **Context:** We use this to ensure the `BioFrame` logic doesn't care if the grammar is stored in S3 or on the local disk.
* **Code:** `app/core/` (Domain), `app/adapters/` (Infrastructure).

### **Hybrid Factory**
* **Definition:** The strategy of combining expert-written grammars (Tier 1) with auto-generated simplified grammars (Tier 3) to achieve 100% language coverage.
* **Context:** Used by the `build_orchestrator.py` to decide which source files to include.

### **Two-Phase Build**
* **Definition:** The compilation strategy used to solve the "Last Man Standing" bug.
    1.  **Verify:** Compile individual languages to temporary object files (`.gfo`).
    2.  **Link:** Merge all valid objects into a single binary (`.pgf`).

---

## 🗣️ Linguistic & GF Terms

### **Abstract Syntax**
* **Definition:** The logical "skeleton" of a grammar. It defines *what* can be said (e.g., "A Sentence consists of a Subject and a Predicate") without defining *how*.
* **Context:** Defined in `gf/AbstractWiki.gf`. It is the language-independent interface.

### **Concrete Syntax**
* **Definition:** The language-specific implementation of the Abstract Syntax. It defines *how* to say it (e.g., "In French, the adjective comes after the noun").
* **Context:** Defined in `WikiFra.gf`, `WikiEng.gf`.

### **Linearization**
* **Definition:** The process of turning a tree structure (Abstract Syntax) into a flat string of text (Concrete Syntax).
* **Context:** This is what the `pgf` C-runtime does when the API is called.

### **Morphology**
* **Definition:** The study of the internal structure of words (inflection).
* **Context:** Handling how "run" becomes "ran" or how "gato" (cat) becomes "gatos" (cats).
* **Code:** Handled by the **RGL** (Tier 1) or simple string concatenation (Tier 3).

### **PGF (Portable Grammar Format)**
* **Definition:** The compiled binary format of a GF grammar. It is to GF what `.class` is to Java.
* **Context:** The file `gf/AbstractWiki.pgf` is the final artifact loaded by the API.

### **RGL (Resource Grammar Library)**
* **Definition:** The standard open-source library for GF that implements the morphology and syntax of ~40 languages.
* **Context:** We use this as our "High Road" (Tier 1) source.

---

## 💾 Data & Logic Terms

### **Domain Sharding**
* **Definition:** Splitting the vocabulary into small, topic-specific files (`science.json`, `people.json`) instead of one giant dictionary.
* **Context:** Optimizes memory usage by only loading relevant terms.

### **Semantic Frame**
* **Definition:** A JSON object representing an abstract intent (e.g., `BioFrame`, `EventFrame`).
* **Context:** This is the input to the API. It is language-agnostic.

### **Saga Pattern**
* **Definition:** A way to manage long-running transactions in a distributed system (e.g., "Start Build" -> "Wait" -> "Update Worker").
* **Context:** Used implicitly by our Async Worker to handle grammar hot-reloading.

### **Tier 1 / Tier 3**
* **Tier 1:** Mature language backed by the RGL. High quality.
* **Tier 3:** "Pidgin" language backed by the Factory. Lower quality (SVO only), but guarantees availability.