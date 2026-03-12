## 7. Renderer

The **Renderer** is the “assembly” layer of SemantiK Architect: it takes an **abstract intent** (meaning) and produces **readable text**.

### What the Renderer is responsible for

- **Turn intent into language output**: the Renderer is where “meaning becomes wording.”
- **Support two input styles (dual-path)**:
  - a **strict/production path** (stable, predictable structured input), and
  - a **prototype path** that can accept a **recursive Ninai-style meaning tree**.
- **Expose two output forms**:
  - **natural language text**, and optionally
  - a **Universal Dependencies (CoNLL-U)** representation for validation/evaluation workflows.

### What the Renderer decides (high level)

- **Which realization strategy to use** for a given language and input (e.g., “high-resource vs long-tail” behavior). This is the practical place where the system chooses between grammar-driven rendering and coverage-oriented fallback approaches.

### What the Renderer does *not* do

- It is **not** the lexicon (it doesn’t define vocabulary).
- It is **not** the grammar matrix (it doesn’t author the linguistic rules).
- It is **not** the context store (it doesn’t own discourse memory; it uses it).

### Why this layer exists

Separating the Renderer makes SemantiK Architect easier to scale:

- You can improve **inputs** (add richer meaning formats) without rewriting lexicon/grammar.
- You can add **outputs** (like UD export) without changing how text is produced.
- You can evolve language strategies while keeping a stable “meaning → text” contract.