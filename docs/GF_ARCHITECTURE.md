
# GF Architecture & Developer Guide

**Version:** 2.1
**Last Updated:** 2025-12-29
**Context:** Abstract Wiki Architect (Python + Grammatical Framework)

## 1. Architectural Overview

This system bridges two fundamentally different paradigms:

1. **Python Domain Layer:** Dynamic, Object-Oriented, String-heavy.
2. **GF Engine Layer:** Statically Typed, Functional, Abstract Syntax Trees.

The critical challenge is the **Type Mismatch**. Python sees `"Marie Curie"` as a string. GF sees it as a specific Lexical Category (e.g., `PN`). Our architecture uses a **"Bridge Pattern"** to wrap raw runtime data into safe GF types before linearization.

### The Stack

| Layer | File/Component | Responsibility |
| --- | --- | --- |
| **Abstract** | `gf/AbstractWiki.gf` | Defines the API contract. The "Schema". |
| **Concrete** | `gf/WikiEn.gf`, `gf/WikiFr.gf` | Implements the schema using the **RGL**. |
| **Library** | `GF Resource Grammar Library` | Provides the linguistic primitives (`mkS`, `mkCl`). |
| **Adapter** | `app/adapters/engines/gf_wrapper.py` | Converts Pydantic Objects → GF Trees. |

---

## 2. Directory Structure & File Hygiene

Strict file naming is enforced to match the compiled PGF binary structure.

### ✅ Allowed Files

* `gf/AbstractWiki.gf` - The Abstract Syntax.
* `gf/WikiEn.gf` - English Concrete Grammar (ISO 639-1 code `en`).
* `gf/WikiFr.gf` - French Concrete Grammar (ISO 639-1 code `fr`).
* `gf/AbstractWiki.pgf` - The compiled binary (Ignored by Git).

### ❌ Prohibited Files (Delete Immediately)

* `gf/Wiki.gf` - Legacy abstract file.
* `gf/WikiEng.gf`, `gf/WikiFra.gf` - Old ISO-3 naming convention.
* `gf/WikiFre.gf` - Incorrect language code (`fre` vs `fr`).
* `gf/Symbolic*.gf` - **CRITICAL:** These local files conflict with the RGL. Always use the system-installed `Symbolic` module.

---

## 3. The "Safe" RGL API (Reference)

We restrict our usage of the GF Resource Grammar Library (RGL) to a specific subset of functions that are proven to be stable for our use case.

### Core Semantic Constructors

| Function | Signature | Description |
| --- | --- | --- |
| `mkS` | `Cl -> S` | Converts a Clause to a Sentence (Tense: Present). |
| `mkCl` | `NP -> VP -> Cl` | Predication ("John walks"). |
| `mkNP` | `Det -> N -> NP` | Determination ("the animal"). |
| `mkVP` | `VP -> NP -> VP` | Transitive Verb Phrase ("loves Paris"). |
| `mkAP` | `A -> AP` | Adjectival Phrase ("blue"). |

### Structural Helpers

| Function | Type | Usage |
| --- | --- | --- |
| `and_Conj` | `Conj` | List conjunction ("X, Y and Z"). |
| `in_Prep` | `Prep` | "in" (English). |
| `symb` | `String -> NP` | **The Type Bridge.** Converts raw strings safely. |

---

## 4. Implementation Rules (The "Anti-Crash" Guide)

These rules exist to bypass known bugs in the GF Compiler (specifically regarding scope resolution and runtime variables).

### Rule #1: The Inlining Rule (Scope Safety)

**Problem:** The compiler crashes with `variable #0 is out of scope` when optimizing `let` bindings involving complex RGL macros.
**Solution:** Never use `let` inside a `lin` rule. Inline all expressions.

* ❌ **Bad (Causes Crash):**

```haskell
mkEvent subj obj =
  let v = mkV "participate"
  in mkS (mkCl subj (mkVP v obj))

```

* ✅ **Good (Safe):**

```haskell
mkEvent subj obj =
  mkS (mkCl subj (mkVP (mkV "participate") obj))

```

### Rule #2: The Symbolic Rule (Gluing Safety)

**Problem:** `mkPN` (Make Proper Name) attempts to apply morphology rules (like English genitive `'s`) to the input string. If the input is a runtime variable, the compiler crashes with `unsupported token gluing`.
**Solution:** Always use `symb` (Symbolic) for raw strings.

* ❌ **Bad:** `mkLiteral s = mkNP (mkPN s)`
* ✅ **Good:** `mkLiteral s = symb s`

### Rule #3: The Modifier Type

**Problem:** `mkS` expects an `Adv` (Sentence-initial/final adverb), not `AdV` (Sentence-middle adverb).
**Solution:** Define `Modifier = Adv`.

---

## 5. The Python Adapter Pattern

The Python wrapper (`gf_wrapper.py`) must manually construct the AST using the "Bridge Functions" defined in the grammar.

### The Mapping Logic

| Python Data | Logic | GF Function | GF Type |
| --- | --- | --- | --- |
| `"Marie"` (Subject) | `to_entity("Marie")` | `mkLiteral` | `Entity` (`NP`) |
| `"Physicist"` (Prop) | `to_prop("Physicist")` | `mkStrProperty` | `Property` (`AP`) |

### Example Python Construction

```python
# Do NOT send raw strings directly to the Grammar Function!
# ❌ Wrong:
# pgf.Expr("mkBio", ["Marie", "Physicist"])

# ✅ Right (Wrap strings in Bridge Functions):
# 1. Create Literal: (mkLiteral "Marie")
subj = pgf.Expr("mkLiteral", [pgf.readExpr('"Marie"')])

# 2. Create Property: (mkStrProperty "Physicist")
prop = pgf.Expr("mkStrProperty", [pgf.readExpr('"Physicist"')])

# 3. Combine
expr = pgf.Expr("mkBio", [subj, prop])

```

---

## 6. Troubleshooting Dictionary

If the build fails, check this table first.

| Error Message | Diagnosis | Fix |
| --- | --- | --- |
| `variable #0 is out of scope` | Compiler failed to resolve `let` variable. | **Inline** the logic (Rule #1). |
| `unsupported token gluing` | `mkPN` used on a variable. | Switch to `symb` (Rule #2). |
| `atomic term conflict` | Local `SymbolicEng.gf` file exists. | **Delete** `gf/Symbolic*.gf`. |
| `Function 'mkBio' not found` | PGF is stale or Language missing. | Recompile + Restart Server. |
| `[mkBio]` (Output Text) | Tree built, but Linearization failed. | Check arguments (arity mismatch). |

---

## 7. Build Commands

We now use the **Two-Phase Build Orchestrator** to handle dependencies and verification.

**1. Clean Environment:**

```bash
# Removes legacy files and clears the cache
rm gf/Symbolic*.gf gf/Wiki*.gf gf/AbstractWiki.pgf

```

**2. Orchestrated Build:**

```bash
# Generates code from Lexicon JSONs -> Validates -> Compiles
python builder/orchestrator.py

```

**3. Test Generation (cURL):**

```bash
curl -X POST "http://localhost:8000/api/v1/generate/fr" \
      -H "Content-Type: application/json" \
      -H "x-api-key: secret" \
      -d '{
            "function": "ninai.constructors.Statement",
            "args": [
              { "function": "ninai.types.Bio" },
              { "function": "ninai.constructors.Entity", "args": ["Q1", "Marie"] },
              { "function": "ninai.constructors.Entity", "args": ["Q2", "physicienne"] },
              { "function": "ninai.constructors.Entity", "args": ["Q3", "française"] }
            ]
          }'

```