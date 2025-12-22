
### 📜 `docs/ADR-001-GF_VERSION_STRATEGY.md`

```markdown
# ADR-001: Strict Adherence to GF v3.12 High-Performance Runtime

**Status:** Accepted  
**Date:** 2025-12-22  
**Context:** Abstract Wiki Architect v2.0 "Omni-Upgrade"

## 1. Context and Problem
The Abstract Wiki Architect relies on the **Grammatical Framework (GF)** for its core linguistic processing. A critical version mismatch exists between our production environment and the upstream library:

* **Production Environment:** Uses **GF v3.12 (C-Runtime)**. This backend is optimized for high-throughput text generation (`libpgf`) and is significantly faster and lighter than the Haskell runtime.
* **Upstream Library:** The `gf-rgl` repository's `master` branch has migrated to **GF v4.0 (Haskell)** syntax (introducing dependent types and token gluing changes).
* **The Error:** Compiling the modern (v4) library with the production (v3) compiler results in `unsupported token gluing` errors, causing High-Resource languages (Tier 1) to fail compilation.

## 2. Decision Options

### Option A: Upgrade to GF v4 (The "Modern" Path)
* **Pros:** Native compatibility with upstream `master` branch; access to academic features (dependent types).
* **Cons:** Requires installing the full Haskell toolchain (GHC/Cabal), adding ~1.5GB of container bloat. Crucially, the Haskell runtime is **~10x slower** than the C-runtime for linearization, violating our API latency requirements.

### Option B: Downgrade Library to v3.12 (The "Stable" Path)
* **Pros:** Preserves the high-speed C-runtime (`libpgf`); zero changes to Docker infrastructure; ensures deterministic builds; matches the `pgf` Python bindings perfectly.
* **Cons:** Cannot use bleeding-edge RGL features (which are unnecessary for Wikipedia text generation).

### Option C: Dynamic Resolution (The "Hybrid" Path)
* **Pros:** Supports both versions via script detection.
* **Cons:** Adds unnecessary complexity. Since we control the infrastructure, supporting a compiler we don't use (v4) is technical debt.

## 3. The Decision
We chose **Option B**.
We prioritize **Runtime Performance** and **Deployment Stability**. The Abstract Wiki Architect will strictly enforce alignment with the **GF v3.12** ecosystem. We reject the "Dynamic Resolution" complexity in favor of a hard lock on the stable release.

## 4. Implementation: The Alignment System
We implemented a unified maintenance script `scripts/align_system.py` that serves as the "Enforcer" of this decision.

**It performs three atomic actions in sequence:**
1.  **Time Travel:** Forcefully resets the `gf-rgl` submodule to commit `e0a2215` (The GF 3.12 Stable release).
2.  **Cache Purge:** Deletes all `.gfo` binaries to prevent version conflict.
3.  **Omni-Bootstrap:** Reads the `everything_matrix.json` registry and auto-generates the "Bridge" files (e.g., `SyntaxEng.gf`) and Application Grammars (e.g., `WikiEng.gf`) for **all** Tier 1 languages.

## 5. Build Workflow (Final)

To build the engine, the workflow is now:

```bash
# 1. Align System (Downgrades RGL & Generates 45+ Language Files)
python3 scripts/align_system.py

# 2. Execute Build (Compiles the PGF binary)
python manage.py build --parallel 8

```

## 6. Consequences

* **Positive:** The build is deterministic and reproducible.
* **Positive:** Compilation time remains fast (C-backend) and text generation latency is minimized.
* **Positive:** "Tier 1" languages (English, French, Chinese, etc.) are fully operational without manual file creation.
* **Negative:** We are "pinned" to the 2024 version of the grammar library. New languages added to RGL in the future must be backported manually if needed.

```

---

### 📝 Update: `docs/00-SETUP_AND_DEPLOYMENT.md`

Replace the "Building" section with this authoritative guide:

```markdown
### 3. System Alignment (Mandatory)
Before building, you must align the external grammar libraries to match the production C-runtime (GF 3.12) and generate the Tier 1 application files.

**Run the Alignment Script:**
```bash
# This downgrades RGL to v3.12 and bootstraps all high-resource languages
python3 scripts/align_system.py

```

*Note: If you skip this step, the build will fail with "unsupported token gluing" errors or "Source not found".*

**Build the Engine:**

```bash
python manage.py build --parallel 8

```

```

```