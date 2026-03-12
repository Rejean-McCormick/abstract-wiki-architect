
# 🧩 RGL Integration & Dynamic Discovery Strategy

**SemantiK Architect — Internal Reference (Everything Matrix / iso2-keyed)**

## 1) The “Naming Mismatch” Problem

Integrating the **GF Resource Grammar Library (RGL)** requires bridging three different naming schemes:

| Layer | Identifier | Example (French) | Example (German) | Example (Chinese) |
|---|---|---|---|---|
| **Semantik Architect (System Keys)** | **ISO-639-1 (iso2, lowercase)** | `fr` | `de` | `zh` |
| **GF RGL (Module Suffix)** | Legacy 2–3-letter suffix | `Fre` | `Ger` | `Chi` |
| **File System** | Folder name | `french` | `german` | `chinese` |

**The conflict:**
You cannot derive RGL module names by capitalizing iso codes.

- `SyntaxFr` (expected) ≠ `SyntaxFre` (actual)
- `SyntaxDe` (expected) ≠ `SyntaxGer` (actual)

Historically, teams tried hardcoded dictionaries or parsing `languages.csv`, but that creates maintenance burden and `languages.csv` is not a reliable ISO translation layer.

---

## 2) The Solution: “Inventory + Normalization” (Everything Matrix Suite)

### Single orchestrator contract

The canonical “refresh” entrypoint is:

- `tools/everything_matrix/build_index.py`

It produces:

- `data/indices/everything_matrix.json` (iso2-keyed)
- It **does not** rescan `gf-rgl/src` during a normal run.
- It treats `data/indices/rgl_inventory.json` as an **input artifact**.

### RGL discovery is isolated in one scanner (debug tool)

The only component that walks `gf-rgl/src` is:

- `tools/everything_matrix/rgl_scanner.py`

It produces the source-of-truth inventory:

- `data/indices/rgl_inventory.json`

**Side-effect policy:**
- Imported as a library: side-effect free by default
- CLI mode can write the inventory when explicitly requested (e.g., `--write`), or when `build_index.py --regen-rgl` is used.

### Canonical normalization

A shared normalization module (e.g., `tools/everything_matrix/norm.py`) is the source of truth for mapping:

- Wiki suffixes / iso3 aliases → canonical **iso2**
- iso2 → display names (when needed)

This makes the system deterministic and avoids “Wiki vs ISO” row mismatches.

---

## 3) Resolution Algorithm Used by the Builder

When the build system needs to compile a language (example: `fr`):

### Step 0: Normalize the requested language key
Normalize any incoming code (`Fre`, `fra`, `fr`) to canonical **iso2** using `config/iso_to_wiki.json`.

**Rule:** the system key is always `iso2` lowercase.

### Step 1: Matrix lookup (iso2 → metadata)
Read `data/indices/everything_matrix.json` for orchestration metadata and readiness signals.

Example (illustrative):
```json
"fr": {
  "meta": { "folder": "french", "origin": "rgl", "tier": 1 }
}
````

### Step 2: Inventory lookup (iso2 → exact RGL module names)

Read `data/indices/rgl_inventory.json` for the exact module set and their real on-disk paths.

Example (illustrative):

```json
"languages": {
  "fr": {
    "path": "gf-rgl/src/french",
    "modules": {
      "Syntax": "gf-rgl/src/french/SyntaxFre.gf",
      "Paradigms": "gf-rgl/src/french/ParadigmsFre.gf"
    },
    "blocks": { "CAT": 10, "NOUN": 10, "PARA": 10, "GRAM": 10, "SYN": 10 }
  }
}
```

**Important:** the builder should not glob `Syntax*.gf` during normal operation; it should trust `rgl_inventory.json` for determinism.

### Step 3: Connector generation (the “Empty Connector” pattern)

Generate the compatibility bridge using the exact discovered module names from the inventory.

Example:

```haskell
-- Generated: WikiFre.gf (suffix derived from inventory)
concrete WikiFre of SemantikArchitect = WikiI ** open SyntaxFre, ParadigmsFre in {
  -- Empty body guarantees compilation success.
  -- Vocabulary is injected at runtime.
}
```

**Why empty bodies:**

* The old approach tried to emit lexical lines (e.g., `mkNP (mkN "animal")`) and failed for languages with different parameterization.
* The new approach guarantees compilation success; runtime lexicon injection handles vocabulary.

### Step 4: Regeneration / self-healing behavior

If `rgl_inventory.json` is missing or stale:

* Preferred: `python tools/everything_matrix/build_index.py --regen-rgl`
* Or debug: `python tools/everything_matrix/rgl_scanner.py --write`

---

## 4) Directory Structure Constraints

This approach assumes a stable repo root and paths derived from the canonical config:

* Canonical config: `data/config/everything_matrix_config.json`
* RGL base path: `gf-rgl/src` (configurable via `rgl_base_path`)

Expected layout:

```text
/ProjectRoot/
├── abstract-wiki-architect/
│   ├── tools/everything_matrix/build_index.py
│   ├── data/config/everything_matrix_config.json
│   └── data/indices/rgl_inventory.json
└── gf-rgl/
    └── src/
        ├── french/
        │   └── SyntaxFre.gf
        └── ...
```

---

## 5) Why this is Robust

1. **Deterministic builds**

* The build uses `rgl_inventory.json`, avoiding “moving target” scans during compilation.

2. **Zero hardcoded mapping tables**

* The only mapping source is `config/iso_to_wiki.json` and the scanner’s on-disk discovery.

3. **Schema-compatible orchestration**

* Everything Matrix keys are canonical iso2, so Zone A/B/C/D land in the same row.

4. **Self-healing via explicit regen**

* If RGL changes module suffixes, re-running the scanner regenerates inventory and downstream connectors without code changes.



