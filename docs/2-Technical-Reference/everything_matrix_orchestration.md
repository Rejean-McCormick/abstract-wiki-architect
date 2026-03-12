# Everything Matrix Orchestration

This document describes the **single-orchestrator** architecture for the Everything Matrix suite.

## Goal

`tools/everything_matrix/build_index.py` is the **only normal entrypoint** that refreshes the full matrix:

* **Zone A**: RGL inventory + grammar completion signals (from `rgl_inventory.json`)
* **Zone B**: Lexicon health
* **Zone C**: App readiness
* **Zone D**: QA readiness

All other scripts in `tools/everything_matrix/` remain available as **debug tools**, and must be:

* **side-effect free by default**
* **not duplicate work** during a normal matrix refresh

---

## Outputs

### Primary output

* `data/indices/everything_matrix.json`

### Cache / fingerprint output

* `data/indices/filesystem.checksum` (or `matrix.output_dir/filesystem.checksum` if configured)

Used to skip work when inputs are unchanged.

### Prerequisite artifacts

* `data/indices/rgl_inventory.json` (Zone A source-of-truth input)

---

## Configuration

### Config file

* `data/config/everything_matrix_config.json`

### Paths controlled by config (typical keys)

* `matrix.output_dir` (default `data/indices`)
* `matrix.everything_index` (default `data/indices/everything_matrix.json`)
* `rgl.inventory_file` (default `data/indices/rgl_inventory.json`)
* `rgl.src_root` (default `gf-rgl/src`)
* `lexicon.lexicon_root` (default `data/lexicon`)
* `qa.gf_root` (default `gf`)
* `frontend.assets_path`, `frontend.profiles_path`
* `backend.profiles_path`
* `iso_map_file` (**should point at** `data/config/iso_to_wiki.json`)

---

## Normalization rules

### Canonical language key

* The matrix is keyed by **ISO-639-1 `iso2`**, **lowercase** (example: `en`, `fr`, `sw`).

### No mixing of key types in orchestrator

* `build_index.py` stores matrix entries under **iso2 only**
* Any wiki/iso3 keys are normalized at scanner boundaries (preferred) or centrally before synthesis

### Source of truth for normalization

`tools/everything_matrix/norm.py` is the shared module for:

* loading `iso_to_wiki.json`
* mapping `wiki` / `iso3` / `WikiXxx` forms → canonical `iso2`
* mapping language display names

**Canonical iso map location** is `data/config/iso_to_wiki.json`. A legacy `config/iso_to_wiki.json` may exist, but new code/config should point to the `data/config/` location.

---

## Scanner contracts

Build Index uses scanners as libraries. The orchestrator calls each scanner **once per zone** (one-shot scan), then performs **dict lookups** per language.

### Zone A — RGL

**Library contract**

* `rgl_scanner.scan_rgl(...) -> inventory_dict`

**Normal behavior**

* `build_index.py` reads `data/indices/rgl_inventory.json`
* It does **not** rescan `gf-rgl/src` unless `--regen-rgl` or inventory missing

**Side effects**

* `rgl_scanner.scan_rgl(write_output=False)` must be side-effect free
* CLI can write with `--write` (debug only)

### Zone B — Lexicon

**Library contract**

* `lexicon_scanner.scan_all_lexicons(lex_root: Path) -> dict[<key>, zone_b_stats]`

**Expected keys**

* `{"SEED": float, "CONC": float, "WIDE": float, "SEM": float}`

**Scale**

* all values are `0..10` floats

### Zone C — App readiness

**Library contract**

* `app_scanner.scan_all_apps(repo_root: Path) -> dict[<key>, zone_c_stats]`

**Expected keys**

* `{"PROF": float, "ASST": float, "ROUT": float}`

**Scale**

* all values are `0..10` (ints/floats allowed; orchestrator clamps)

### Zone D — QA readiness

**Library contract**

* `qa_scanner.scan_all_artifacts(gf_root: Path) -> dict[<key>, zone_d_stats]`

**Expected keys**

* `{"BIN": float, "TEST": float}`

**Scale**

* all values are `0..10` floats

> Note: Scanners may emit keys as iso2/wiki/iso3 forms; `build_index.py` normalizes keys to iso2 before writing the matrix.

---

## Orchestrator behavior

`tools/everything_matrix/build_index.py` performs:

1. **fingerprint/cache check** (skips work on cache hit unless forced)
2. ensures prerequisite inventories exist (optionally regenerates)
3. runs **one-shot scans** for each zone
4. synthesizes per-language verdict + maturity
5. writes `data/indices/everything_matrix.json`
6. writes the new fingerprint to `filesystem.checksum`

### Cache hit semantics

* Default: if fingerprint matches, **returns early**
* With `--touch-timestamp`: rewrites only the matrix timestamp fields on cache hit
* With `--force` (or any `--regen-*`): bypasses cache

### One-shot scan rule

During a normal refresh, build_index calls:

* `lexicon_scanner.scan_all_lexicons(...)` **once**
* `app_scanner.scan_all_apps(...)` **once**
* `qa_scanner.scan_all_artifacts(...)` **once**

Inside the per-language loop it does **only dict lookups**.

### No duplicate RGL scans

During a normal refresh, build_index:

* does **not** call `rgl_scanner.scan_rgl()` unless explicitly requested (`--regen-rgl`) or the inventory file is missing

---

## Scoring rules

### Scale

All zone values are clamped to `0..10`.

### Back-compat shim

`build_index.py` may rescale legacy `0..1` values into `0..10`, but scanners should emit `0..10`.

### Zone averages

Per-language averages are computed as mean of each zone's sub-blocks:

* `A_RGL` average of `CAT, NOUN, PARA, GRAM, SYN`
* `B_LEX` average of `SEED, CONC, WIDE, SEM`
* `C_APP` average of `PROF, ASST, ROUT`
* `D_QA` average of `BIN, TEST`

### Maturity

Maturity is a weighted sum of the zone averages:

* weights live in `data/config/everything_matrix_config.json` (under `matrix.zone_weights` or equivalent)
* output is clamped to `0..10`

### Strategy ladder

The orchestrator produces one of:

* `HIGH_ROAD`
* `SAFE_MODE`
* `SKIP`

(Exact thresholds are configured in the matrix config.)

---

## Downstream consumer: Grammar build orchestrator

The Everything Matrix **does not compile grammars**. It produces per-language `build_strategy` (and supporting signals) that downstream build tooling consumes.

Canonical grammar build entrypoints:

* **Programmatic**: `builder.orchestrator.build_pgf(...)`
* **CLI**: `python -m builder.orchestrator ...` (preferred)
* **Legacy shim** (if present): `gf/build_orchestrator.py` (wrapper only)

---

## CLI usage

### Normal run

```bash
python tools/everything_matrix/build_index.py
```

### Force rebuild (bypass cache)

```bash
python tools/everything_matrix/build_index.py --force
```

### Regenerate only the prerequisite RGL inventory (and rebuild)

```bash
python tools/everything_matrix/build_index.py --regen-rgl
```

### Force-rescan specific zones (and rebuild)

```bash
python tools/everything_matrix/build_index.py --regen-lex
python tools/everything_matrix/build_index.py --regen-app
python tools/everything_matrix/build_index.py --regen-qa
```

### Cache hit but refresh timestamps

```bash
python tools/everything_matrix/build_index.py --touch-timestamp
```

### Verbose logging

```bash
python tools/everything_matrix/build_index.py --verbose
```
