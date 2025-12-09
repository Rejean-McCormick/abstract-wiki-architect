Here is the **Master Glossary** for the Abstract Wiki Architect (V2). This consolidates all the concepts discussed into a single reference guide, organized by function.

---

### 🏗️ 1. The Architecture ("The Refinery")
*The high-level design that treats language generation as a manufacturing pipeline.*

* **The Refinery:** The overall V2 architecture. It accepts raw language data, processes it through different tiers of quality, and outputs a usable grammar database.
* **Tier 1 (RGL - Gold Standard):** Languages supported by the official *Grammatical Framework Resource Grammar Library*. These have perfect morphology and syntax (e.g., English, French, Finnish).
* **Tier 2 (Contrib - Silver/Manual):** Languages that started as Tier 3 but were improved by AI or humans. These files live in `gf/contrib/` and override Tier 3.
* **Tier 3 (Factory - Bronze/Pidgin):** Languages generated programmatically by `grammar_factory.py`. They use simple string concatenation (SVO word order) to ensure 100% API coverage, even if the grammar is rough.
* **The Orchestrator:** The `gf/build_orchestrator.py` script. It acts as the project manager, deciding which Tier to use for each language and compiling them into the final database.

---

### 🧠 2. Grammatical Framework ("The Engine")
*The specific software technology (GF) powering the linguistics.*

* **Abstract Grammar (`AbstractWiki.gf`):** The "Interface." It defines *what* can be said (functions like `mkFact` and categories like `Entity`) but not *how* to say it. It is language-independent.
* **Concrete Grammar (`WikiEng.gf`, `WikiZul.gf`):** The "Implementation." It maps the Abstract rules to specific words and word orders for a specific language.
* **PGF (`Wiki.pgf`):** *Portable Grammar Format*. The compiled binary file (like a `.exe` or `.dll`). The Python API loads this file to generate text.
* **Linearization:** The process of turning a semantic tree (Abstract) into a text string (Concrete).
* **Smart Paradigms (`mkN`, `mkV`):** "Magic" functions in the RGL that try to guess all forms of a word (plural, past tense, etc.) based on just one dictionary form. (The source of the Russian build error).
* **Coercion:** A linguistic trick used to force one category into another (e.g., turning a Noun Phrase into an Adverbial Phrase using a Preposition).

---

### ⚙️ 3. The Build Process ("The Assembly Line")
*How code turns into the runnable engine.*

* **Vocabulary Stubs:** A minimal list of words (like "animal" and "walk") used to test if a language module is valid during the build.
* **Permissive Mode:** A build strategy where the Orchestrator skips languages that fail to compile (logging the error), rather than stopping the entire process.
* **Pidgin:** The output style of Tier 3 languages. It lacks complex grammar (agreement, conjugation) but conveys meaning clearly (e.g., "Shaka IS Warrior").
* **Build Logs:** JSON or text files generated during the build that detail exactly why a specific language failed, used for debugging.

---

### 🗄️ 4. Data Sources & Semantics ("The Inputs")
*The raw information fed into the system.*

* **Wikidata (Q-Items):** The global knowledge base used as the source of truth. `Q42` -> *Douglas Adams*.
* **Abstract Wikipedia (Z-Objects):** The theoretical format for language-independent content. Our system is a renderer for this concept.
* **Frame:** The JSON object sent by the frontend (e.g., `{ "type": "bio", "name": "Shaka" }`). It represents the *meaning* the user wants to express.
* **Ontology:** The map of "what exists." Defined by our schemas (e.g., a "Person" has a "Birth Date").
* **AST (Abstract Syntax Tree):** The strict, tree-like structure required by GF. The "Frame" is converted into an "AST" before generation.
* **Lexicon:** The dictionary database mapping concepts (Q-Items) to words in target languages.

---

### 💻 5. Runtime & API ("The Application")
*The live software running on the server.*

* **NLG Client:** The Python service (`services/nlg_client.py`) that holds the PGF file in memory and answers API requests.
* **Bridge (The Mapper):** The logic (`semantics/aw_bridge.py`) that converts the user's JSON Frame into a GF Abstract Syntax Tree.
* **Real-Time Realization:** The feature where text updates instantly in 300 languages as the user types.
* **Hot-Reloading:** The ability of the server to detect a new `Wiki.pgf` (after a build) and load it without crashing.
* **Endpoint:** A specific URL function, e.g., `POST /generate` (make text) or `POST /grammar/refine` (fix code).

---

### 🧪 6. Quality & Refinement ("The Loop")
*How the system improves over time.*

* **Smoke Test:** A basic test (`test_gf_dynamic.py`) to ensure the engine starts and can generate *something*.
* **Gold Standard:** A list of human-written "perfect" translations used to benchmark the system's output.
* **AI Refiner:** An offline tool (`utils/ai_refiner.py`) that uses an LLM (Gemini) to read a crude Tier 3 grammar and rewrite it as a better Tier 2 grammar.
* **Repair Ticket:** The concept of flagging a specific language error so the AI Refiner can attempt to fix it in the next build cycle.