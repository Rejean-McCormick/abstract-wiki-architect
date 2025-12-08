# 📘 Abstract Wiki Architect: Multilingual Engine V2

**Version:** 2.0 (The Refinery)
**Status:** Approved for Implementation
**Objective:** Scale language support from ~40 (Official RGL) to 300+ (Global Coverage) using a Hybrid AI/Factory approach.

-----

## 1. The "Three-Tier" Philosophy

To support 300 languages immediately without waiting for 300 academic linguists, we utilize a **Waterfall Priority System**. The build system selects the best available grammar source for every language code.

| Tier | Name | Source Path | Description |
| :--- | :--- | :--- | :--- |
| **🥇 1** | **Official RGL** | `gf/gf-rgl/src/` | **Gold Standard.** Expert-written grammars (English, French, Chinese). Used automatically if present. |
| **🥈 2** | **Contrib** | `gf/contrib/` | **Manual Overrides.** High-quality community contributions or specific fixes that override the Factory or RGL. |
| **🥉 3** | **Factory** | `gf/generated/src/` | **The Safety Net.** Programmatically generated "Pidgin" grammars (SVO/SOV templates) to ensure 100% API coverage. |

-----

## 2. System Architecture & Data Flow

The system functions as a **Linguistic Refinery**. Languages start as raw "DNA" configurations and are processed into compiled binary code.

```mermaid
graph TD
    A[Configuration: FACTORY_CONFIGS] -->|Input| B(utils/grammar_factory.py)
    B -->|Generates| C[gf/generated/src/]
    
    D[Official GF-RGL Repo] -->|Read| E(gf/build_orchestrator.py)
    F[Manual Contrib Folder] -->|Read| E
    C -->|Read| E
    
    E -->|Waterfall Selection| G{Compile Decision}
    G -->|Tier 1 Found?| H[Use RGL]
    G -->|Tier 2 Found?| I[Use Contrib]
    G -->|Tier 3 Found?| J[Use Factory]
    
    H & I & J -->|gf -make| K[Wiki.pgf Binary]
    
    L[API Request 'zul'] -->|Lookup| M(language_map.py)
    M -->|Load Concrete| K
````

-----

## 3\. The File Arborescence (Directory Structure)

This structure separates **Logic** (scripts) from **Data** (grammars) and **Generated Artifacts**.

```text
C:\MyCode\AbstractWiki\abstract-wiki-architect\
│
├── docs\
│   └── ARCHITECTURE_V2.md        # [THIS FILE] The Master Spec
│
├── docker\
│   └── Dockerfile.backend        # [ENV] Copies gf-rgl, contrib, and generated folders
│
├── architect_http_api\
│   └── gf\
│       └── language_map.py       # [ROUTER] Maps ISO codes/Z-IDs to Concrete Grammar Names
│
├── gf\
│   ├── Wiki.pgf                  # [ARTIFACT] The final compiled binary
│   ├── build_orchestrator.py     # [LOGIC] Replaces build_300.py. Runs the Waterfall build.
│   │
│   ├── gf-rgl\                   # [DATA - TIER 1] Official Read-Only Repo
│   │
│   ├── contrib\                  # [DATA - TIER 2] Manual Overrides
│   │   └── que\                  #     e.g., specific Quechua fix
│   │       └── WikiQue.gf
│   │
│   └── generated\                # [DATA - TIER 3] Factory Output (Auto-Cleaned)
│       └── src\
│           ├── zul\              #     -> Auto-created Zulu
│           └── yor\              #     -> Auto-created Yoruba
│
├── utils\
│   ├── grammar_factory.py        # [LOGIC] The Generator. Writes Tier 3 files.
│   └── ai_refiner.py             # [LOGIC] The Upgrader. Sends drafts to Gemini for improvements.
│
└── test_gf_dynamic.py            # [TEST] Validates that ALL 300 languages produce text.
```

-----

## 4\. Variable Definitions: The Language "DNA"

The `FACTORY_CONFIGS` dictionary inside `utils/grammar_factory.py` is the **Source of Truth** for the 260+ missing languages.

**Variable Structure:**

  * **Key:** ISO 639-3 Code (lowercase).
  * **Value:** Dictionary containing:
      * `name`: CamelCase Name (Used for file generation `WikiZulu`).
      * `order`: Syntax Template (`SVO`, `SOV`, `VSO`).
      * *(Future)* `features`: List of morphological tags (e.g., `["agglutinative", "tonal"]`) for the AI Refiner.

### The Initial Configuration (V1 Snapshot)

We define the "Missing Middle" languages here. This list will grow to 300.

```python
# utils/grammar_factory.py CONFIGURATION

FACTORY_CONFIGS = {
    # --- AFRICA (Bantu / Niger-Congo / Afroasiatic) ---
    "zul": {"name": "Zulu",        "order": "SVO"},
    "xho": {"name": "Xhosa",       "order": "SVO"},
    "yor": {"name": "Yoruba",      "order": "SVO"},
    "ibo": {"name": "Igbo",        "order": "SVO"},
    "hau": {"name": "Hausa",       "order": "SVO"},
    "swa": {"name": "Swahili",     "order": "SVO"}, # Fallback
    "wol": {"name": "Wolof",       "order": "SVO"},
    "kin": {"name": "Kinyarwanda", "order": "SVO"},
    "lug": {"name": "Ganda",       "order": "SVO"},
    "lin": {"name": "Lingala",     "order": "SVO"},
    "som": {"name": "Somali",      "order": "SOV"}, # Somali is often SOV

    # --- ASIA (Austronesian / Dravidian / Turkic) ---
    "kor": {"name": "Korean",      "order": "SOV"},
    "ind": {"name": "Indonesian",  "order": "SVO"},
    "msa": {"name": "Malay",       "order": "SVO"},
    "tgl": {"name": "Tagalog",     "order": "VSO"}, # Verb-Initial
    "vie": {"name": "Vietnamese",  "order": "SVO"},
    "jav": {"name": "Javanese",    "order": "SVO"},
    "tam": {"name": "Tamil",       "order": "SOV"},
    "tel": {"name": "Telugu",      "order": "SOV"},
    "ben": {"name": "Bengali",     "order": "SOV"},
    "uzb": {"name": "Uzbek",       "order": "SOV"},
    "kaz": {"name": "Kazakh",      "order": "SOV"},

    # --- AMERICAS (Indigenous) ---
    "que": {"name": "Quechua",     "order": "SOV"},
    "aym": {"name": "Aymara",      "order": "SOV"},
    "nav": {"name": "Navajo",      "order": "SOV"},
    "grn": {"name": "Guarani",     "order": "SVO"},
    "nah": {"name": "Nahuatl",     "order": "VSO"}, # Classical

    # --- EUROPE / MIDDLE EAST (Minor / Isolate) ---
    "fry": {"name": "Frisian",     "order": "SVO"},
    "bre": {"name": "Breton",      "order": "SVO"}, # V2 actually, but SVO is close approximation
    "oci": {"name": "Occitan",     "order": "SVO"},
    "gla": {"name": "Gaelic",      "order": "VSO"}, # Scottish Gaelic
    "cym": {"name": "Welsh",       "order": "VSO"},
    "eus": {"name": "Basque",      "order": "SOV"}, # Fallback if RGL fails
    "tat": {"name": "Tatar",       "order": "SOV"},
    "kur": {"name": "Kurdish",     "order": "SOV"},
}
```

-----

## 5\. The Workflow: From Draft to Gold

This defines how we use AI to improve the system over time.

### Phase 1: Injection (Today)

1.  **Developer:** Updates `FACTORY_CONFIGS` in `grammar_factory.py`.
2.  **System:** Generates simple `WikiZul.gf` (SVO string concatenation).
3.  **Result:** API serves Zulu immediately (Quality: Low, Availability: 100%).

### Phase 2: AI Refinement (Tomorrow)

1.  **Script:** `utils/ai_refiner.py` selects a generated language (e.g., `zul`).
2.  **Prompt:** Sends the generated `SyntaxZul.gf` + a glossary to Gemini.
      * *"Gemini, this is a skeleton Zulu grammar. Zulu uses Noun Classes (prefixes). Please refactor the `ResZulu` module to include a `Class` parameter and update `mkN` to handle basic prefixes."*
3.  **Review:** Gemini returns updated code.
4.  **Action:** The script saves this new code into `gf/contrib/zul/` (Tier 2).
5.  **Build:** The Orchestrator automatically detects the Tier 2 file and uses it instead of the Factory file.

### Phase 3: Graduation (Future)

1.  **Linguist:** specific contribution fixes edge cases in `gf/contrib/zul`.
2.  **Action:** We submit a Pull Request to the official `GrammaticalFramework/gf-rgl` repository.
3.  **Success:** Zulu is merged into RGL. We delete `gf/contrib/zul` and `gf/generated/zul`. The system now uses Tier 1 automatically.

-----

## 6\. Implementation Steps

1.  **Generate Factory:** Run `grammar_factory.py` to populate `gf/generated`.
2.  **Run Orchestrator:** Run `build_orchestrator.py` to compile `Wiki.pgf`.
3.  **Deploy:** Restart Docker Backend.
4.  **Verify:** Call `test_gf_dynamic.py` to ensure all 50+ defined languages respond to "The cat walks."

