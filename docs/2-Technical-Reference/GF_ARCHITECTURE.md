# GF Architecture & Developer Guide

**Version:** 2.3  
**Last Updated:** 2026-02-20  
**Context:** SemantiK Architect (Python + Grammatical Framework)

## 1. Architectural Overview

This system bridges two fundamentally different paradigms:

1. **Python Domain Layer:** Dynamic, object-oriented, string-heavy.
2. **GF Engine Layer:** Statically typed, functional abstract syntax trees.

The critical challenge is the **type mismatch**. Python sees `"Marie Curie"` as a string. GF sees a typed term (e.g., `NP`, `PN`, etc.). Our architecture uses a **Bridge Pattern**: raw runtime data is wrapped into safe GF types before linearization.

### The Stack

| Layer | File/Component | Responsibility |
| --- | --- | --- |
| **Abstract** | `gf/semantik_architect.gf` | Defines the API contract (schema). |
| **Concrete (App Grammars)** | `gf/Wiki{WikiCode}.gf` | Implements the schema using the RGL (one per language). |
| **Bridge (Syntax Instances)** | `generated/src/Syntax{RglCode}.gf` | Provides `Syntax{RglCode}` instances used by app grammars. |
| **Library** | GF Resource Grammar Library (RGL) | Linguistic primitives (`mkS`, `mkCl`, etc.). |
| **Adapter** | `app/adapters/engines/gf_wrapper.py` | Converts Pydantic objects → GF trees (PGF expressions). |

---

## 2. Naming: ISO vs WikiCode vs RglCode (Source of Most Bugs)

### Canonical rule: naming is driven by `data/config/iso_to_wiki.json`

Confirmed mappings in this repo:

- `en` → `{"wiki": "Eng"}` → app grammar is `gf/WikiEng.gf`
- `fr` → `{"wiki": "Fre"}` → app grammar is `gf/WikiFre.gf`

**Implication:** this codebase does **not** use `WikiEn.gf` / `WikiFr.gf`. ISO-2 codes do not appear directly in grammar filenames.

### Terms

- **ISO**: `en`, `fr`, `de` (ISO-639-1)
- **WikiCode**: `Eng`, `Fre`, `Ger`, … (from `iso_to_wiki.json`)
- **RglCode**: `Eng`, `Fre`, `Ger`, … (typically matches WikiCode here)

---

## 3. Directory Structure & File Hygiene

The system historically used two “generated” roots:

- `generated/src` (**canonical**)
- `gf/generated/src` (**legacy**)

On Windows-mounted filesystems (`/mnt/c/...`), symlinks can be unreliable. The commander supports both, but you must treat **`generated/src` as canonical**.

### ✅ Allowed / Canonical

- `gf/semantik_architect.gf` — abstract syntax
- `gf/Wiki{WikiCode}.gf` — app concrete grammars (e.g., `gf/WikiEng.gf`, `gf/WikiFre.gf`)
- `generated/src/Syntax{RglCode}.gf` — bridge “Syntax instances” (e.g., `generated/src/SyntaxEng.gf`)
- `gf/semantik_architect.pgf` — compiled binary (usually git-ignored)
- `data/config/iso_to_wiki.json` — authoritative mapping (ISO → WikiCode)

### ⚠️ Allowed but Legacy (should be unified)

- `gf/generated/src/*` — legacy generated location  
  Prefer to keep it a symlink to `generated/` if your FS supports symlinks; otherwise keep it synchronized and do not hand-edit.

### ❌ Prohibited / Remove or Avoid Creating

- `gf/Wiki.gf` — legacy/ambiguous
- `gf/WikiEn.gf`, `gf/WikiFr.gf` — wrong naming convention for this repo
- `gf/Symbolic*.gf` — **CRITICAL:** local files can conflict with the RGL’s `Symbolic` modules
- Any `*.RGL_BROKEN` variants under include paths — can shadow correct modules depending on search path order

**Important:** if you see “Generated dirs distinct” warnings, assume there is risk of stale/shadowing modules until unified.

---

## 4. RGL Version Pinning (Alignment Contract)

This project relies on a pinned RGL state to avoid “API drift” errors in `Syntax.gf` and other RGL modules.

### Contract

- `builder/orchestrator.py` refuses to compile if `gf-rgl` is not pinned to the expected ref.
- `python manage.py align --force` is the canonical way to pin RGL and regenerate Tier-1 bridges/app grammars.

### Practical guidance

- Treat `gf-rgl/` as a normal git repo clone (submodule configuration is not assumed).
- Pin by **ref** (tag/branch/commit), not a “magic commit prefix”.
- Prefer a stable ref such as `release-3.12` (or the project’s configured ref), overridable via `ABSTRACTWIKI_RGL_REF`.

---

## 5. The “Safe” RGL API (Reference)

We restrict our RGL usage to a stable subset.

### Core Semantic Constructors

| Function | Signature | Description |
| --- | --- | --- |
| `mkS` | `Cl -> S` | Clause → Sentence |
| `mkCl` | `NP -> VP -> Cl` | Predication (“John walks”) |
| `mkNP` | `Det -> N -> NP` | Determination (“the animal”) |
| `mkVP` | `V2 -> NP -> VP` or `VP -> NP -> VP` | Transitive VP |
| `mkAP` | `A -> AP` | Adjectival phrase |

### Structural Helpers

| Function | Type | Usage |
| --- | --- | --- |
| `and_Conj` | `Conj` | List conjunction |
| `in_Prep` | `Prep` | “in” |
| `symb` | `String -> NP` | **Type bridge** for raw strings |

> Note: the exact module providing `symb` depends on RGL version; do not shadow `Symbolic*` locally.

---

## 6. Implementation Rules (Anti-Crash / Stability Rules)

These rules exist because some GF compiler + RGL macro patterns can produce unstable compilation behavior.

### Rule #1: Inlining Rule (Scope Safety)

Avoid `let` inside `lin` rules when composing complex RGL macros.

**Bad:**
```haskell
mkEvent subj obj =
  let v = mkV "participate"
  in mkS (mkCl subj (mkVP v obj))
````

**Good:**

```haskell
mkEvent subj obj =
  mkS (mkCl subj (mkVP (mkV "participate") obj))
```

### Rule #2: Symbolic Rule (Runtime String Safety)

Do not run morphology over runtime variables with `mkPN`/`mkN` when the input is unknown at compile time.

**Bad:** `mkLiteral s = mkNP (mkPN s)`
**Good:** `mkLiteral s = symb s`

### Rule #3: Modifier Type Rule

If you define a `Modifier`, use `Adv` (not `AdV`) unless you have a controlled, language-specific reason.

---

## 7. The Python Adapter Pattern

The Python wrapper (`gf_wrapper.py`) must construct ASTs using grammar bridge functions, not raw strings directly.

```python
# Wrong: raw strings passed directly
# pgf.Expr("mkBio", ["Marie", "Physicist"])

# Right: wrap strings using bridge constructors that exist in semantik_architect.gf
subj = pgf.Expr("mkLiteral", [pgf.readExpr('"Marie"')])
prop = pgf.Expr("mkStrProperty", [pgf.readExpr('"Physicist"')])
expr = pgf.Expr("mkBio", [subj, prop])
```

**Rule:** the adapter must match the exact function names + arities in `gf/semantik_architect.gf`.

---

## 8. Troubleshooting Dictionary

| Symptom / Error                                                            | Diagnosis                                           | Fix                                                                   |
| -------------------------------------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------- |
| `Cannot connect to the Docker daemon at unix:///var/run/docker.sock` (WSL) | Linux docker socket not connected to Docker Desktop | Use `docker.exe` from WSL or enable Docker Desktop WSL integration.   |
| `gf-rgl is not pinned to the expected ...`                                 | RGL pin mismatch                                    | `python manage.py align --force` then build.                          |
| `SyntaxX.gf does not exist`                                                | Missing bridge instance for a Tier language         | `python tools/bootstrap_tier1.py --force` (or `manage.py align`).     |
| `atomic term conflict` / `Symbolic*` conflicts                             | Local `Symbolic*.gf` shadowing RGL                  | Delete local `gf/Symbolic*.gf`.                                       |
| `Function ... not found`                                                   | PGF stale or wrong grammar set compiled             | Rebuild PGF and restart API.                                          |
| “Generated dirs distinct” warnings                                         | `generated/src` and `gf/generated/src` diverged     | Prefer `generated/src`; unify/sync legacy; avoid editing legacy path. |

---

## 9. Build Commands (Current Canonical Flow)

### Always build in WSL (recommended)

The default `manage.py` configuration uses Linux venv paths (`venv/bin/python`). Running `manage.py build` in Windows PowerShell will fail unless you provide a Windows venv layout and/or a Windows-aware venv resolver.

### Minimal “Known Good” Flow (Tier-1, small set)

```bash
# 1) Align (pins gf-rgl + generates Tier-1 bridges/app grammars)
python manage.py align --force

# 2) Build only a small language set while iterating
python manage.py build --langs en fr
```

### If you need to refresh RGL inventory for the matrix

```bash
python tools/everything_matrix/build_index.py --regen-rgl
python tools/bootstrap_tier1.py --force
```

### Cleaning

Do **not** delete all `gf/Wiki*.gf` anymore—those are canonical app grammars in this repo (WikiCode naming).
Prefer:

```bash
python manage.py clean
```

If you must do a manual clean, focus on compiled artifacts (`*.gfo`, `*.pgf`) and generated outputs, not source grammars.

