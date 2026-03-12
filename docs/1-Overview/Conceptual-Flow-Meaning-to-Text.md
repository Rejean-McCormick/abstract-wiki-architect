# 4. Conceptual Flow: Meaning → Text

SemantiK Architect is **generation-first**: it does not “interpret” text. It takes an **unambiguous meaning payload** and renders it into surface language.

## Flow (at a glance)

**Meaning (Frame or Ninai)** → **Normalize meaning** → **Apply discourse context (optional)** → **Pick language strategy (tier)** → **Realize text (lexicon + grammar)** → **Export (text, optionally UD)** → **Quality checks (optional)**

## Step-by-step

1. **Provide meaning (input)**  
   SemantiK Architect accepts meaning in two shapes:
   - a **strict, flat semantic frame** (stable production input)
   - a **recursive Ninai-style object tree** (more expressive, experimental input)

2. **Normalize meaning (adapter stage)**  
   Inputs are normalized into an internal “intent” representation:
   - validate required fields / structure
   - resolve defaults and normalize naming
   - if the input is Ninai-style, an adapter walks the object tree and converts it into the internal intent/frame representation (a recursive object-walker approach, not text parsing)

3. **Use context for multi-sentence coherence (optional but important for naturalness)**  
   If a session is active, the system can track what entity is “in focus” and apply simple discourse decisions (e.g., reducing repeated names via pronouns when appropriate).

4. **Select a language strategy (coverage vs precision)**  
   To cover both high-resource and long-tail languages, the renderer selects a tiered strategy:
   - a higher-precision **rule-based** path (when strong grammar resources exist)
   - a broader-coverage **factory/topology-based** fallback (when they don’t)
   - optional manual overrides can take precedence when available

5. **Realize the sentence (meaning → surface text)**  
   Rendering is the assembly step that combines:
   - **lexical choice** (words and their properties)
   - **grammar / linearization** (how those words become a correct sentence in the target language)

6. **Export (outputs)**  
   The primary output is **natural language text**. Optionally, the system can also output a **Universal Dependencies (CoNLL-U) view** for validation and evaluation.

7. **Close the loop with quality checks (optional workflow)**  
   A QA loop can compare generated output against a **gold standard** and flag regressions (including automated reporting workflows), so improvements remain stable over time.