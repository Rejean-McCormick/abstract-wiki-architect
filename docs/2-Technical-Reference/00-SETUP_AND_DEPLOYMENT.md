# 🛠️ Setup & Deployment Guide

**SemantiK Architect v2.5**

This guide covers installation, configuration, and deployment of the SemantiK Architect. Because the core engine depends on **Grammatical Framework (GF)** C-libraries (`libpgf`), the backend **must run in a Linux environment**.

For developers on Windows, the recommended setup is a **Hybrid Architecture**:

1. **Windows 11:** Source code editing (VS Code), Git operations, Frontend execution.
2. **WSL 2 (Ubuntu):** Backend execution, Python environment, Redis, and GF compilation.

---

## 1. Prerequisites

Ensure you have:

* **Windows 10/11** with **WSL 2** enabled.
* **Ubuntu 22.04 LTS** (or newer) installed from the Microsoft Store.
* **Docker Desktop** (configured to use the WSL 2 backend).
* **VS Code** with the **"WSL"** extension installed.
* **Node.js 18+** installed on Windows (Frontend).

---

## 2. Directory Structure & Pathing

To avoid path issues, keep the repo on your Windows drive so both Windows and WSL can access it.

* **Windows Path:** `C:\MyCode\SemantiK_Architect\`
* **WSL Path:** `/mnt/c/MyCode/SemantiK_Architect/`

**Recommended Layout:**

```text
/mnt/c/MyCode/SemantiK_Architect/
├── abstract-wiki-architect/      <-- [REPO ROOT]
│   ├── .env                      <-- Env variables (WSL-side)
│   ├── config/                   <-- Preferred config location (if present)
│   ├── data/
│   │   ├── config/               <-- Fallback config location (if used)
│   │   ├── indices/              <-- Everything Matrix outputs
│   │   │   └── everything_matrix.json
│   │   └── lexicon/              <-- Lexicon store (by ISO-2)
│   │       ├── en/
│   │       ├── fr/
│   │       └── ...
│   ├── gf/
│   │   └── semantik_architect.pgf      <-- Generated binary
│   └── ...
└── gf-rgl/                       <-- [EXTERNAL] GF Resource Grammar Library
    └── src/
```

> **⚠️ CRITICAL:** If you plan to edit files in Windows, do not clone the repo into the Linux-native filesystem (`~/...`). Clone it on `C:` so both OSs share the same working tree.

---

## 3. System Initialization (WSL)

Open **Ubuntu/WSL Terminal** (not PowerShell) and go to the repo root:

```bash
cd /mnt/c/MyCode/SemantiK_Architect/Semantik_architect
```

### Step A: Install C-Library Dependencies

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential libgmp-dev
sudo apt install -y dos2unix
```

### Step B: Install the GF Compiler

```bash
wget https://www.grammaticalframework.org/download/gf-3.12-ubuntu-22.04.deb
sudo apt install ./gf-3.12-ubuntu-22.04.deb
gf --version
```

### Step C: Setup the Resource Grammar Library (RGL)

```bash
cd ..
git clone https://github.com/GrammaticalFramework/gf-rgl.git

cd gf-rgl
dos2unix Setup.sh
chmod +x Setup.sh
sudo ./Setup.sh
```

---

## 4. Python Environment (WSL)

Run inside `abstract-wiki-architect`:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 5. Configuration (`.env`)

Create a `.env` file in the repo root.

**File:** `.env`

```ini
# --- Application Meta ---
APP_NAME=abstract-wiki-architect
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
LOG_FORMAT=console

# --- Persistence ---
# Repo root used by the Tools Router to confine execution to this directory
FILESYSTEM_REPO_PATH=/mnt/c/MyCode/SemantiK_Architect/Semantik_architect

# --- Grammar Engine ---
GF_LIB_PATH=/mnt/c/MyCode/SemantiK_Architect/gf-rgl
PGF_PATH=/mnt/c/MyCode/SemantiK_Architect/Semantik_architect/gf/semantik_architect.pgf

# --- Messaging & State (Redis) ---
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SEC=600

# --- Worker ---
WORKER_CONCURRENCY=2

# --- Tools Router (Admin-only execution) ---
# Output + timeout controls for tool subprocess runs
ARCHITECT_TOOLS_MAX_OUTPUT_CHARS=200000
ARCHITECT_TOOLS_DEFAULT_TIMEOUT_SEC=600

# AI-gated tools (e.g., ambiguity_detector, seed_lexicon, ai_refiner)
ARCHITECT_ENABLE_AI_TOOLS=0

# --- DevOps / AI (only if you use these features) ---
GITHUB_TOKEN=your_github_pat_token
REPO_URL=https://github.com/your-org/abstract-wiki-architect
GOOGLE_API_KEY=your_gemini_api_key
AI_MODEL_NAME=gemini-1.5-pro
```

Notes:

* Lexicon directories are stored under `data/lexicon/{iso2}/…` (ISO-639-1 / ISO-2).
* Some tools load language mappings from `config/iso_to_wiki.json` if present; otherwise they fall back to `data/config/iso_to_wiki.json`.

---

## 6. Running Locally (Hybrid Mode)

You can run the stack manually, or use the launcher.

### Option A: Unified launcher (recommended)

Run:

```powershell
.\Run-Architect.ps1
```

This handles process cleanup and spawns API, Worker, and Frontend in separate windows.

### Option B: Manual (4 terminals)

#### Terminal 1: Redis (PowerShell or WSL)

```powershell
docker run -p 6379:6379 --name aw_redis -d redis:alpine
```

#### Terminal 2: API Backend (WSL)

```bash
source venv/bin/activate
uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

#### Terminal 3: Async Worker (WSL)

```bash
source venv/bin/activate
arq app.workers.worker.WorkerSettings --watch app
```

#### Terminal 4: Frontend (Windows PowerShell)

```powershell
cd architect_frontend
npm install
npm run dev
```

UI:

* `http://localhost:3000/semantik_architect`
  Developer Console:
* `http://localhost:3000/semantik_architect/dev`
  Tools Dashboard:
* `http://localhost:3000/semantik_architect/tools`

---

## 7. Production Deployment (Docker)

Use `docker-compose` for production or full-stack container testing.

Key differences:

* **Pathing:** compose mounts the repo into the backend container.
* **Networking:** services use hostnames (`redis`, `backend`, `frontend`), not `localhost`.
* **Base path:** UI served under `/semantik_architect`; API under `/semantik_architect/api/v1`.

### Build and run

```bash
docker-compose up --build -d
```

### Verify

```bash
docker-compose ps
```

---

## 8. Troubleshooting

### "pgf module not found"

* Cause: running Python on Windows or failing to compile the C-extension.
* Fix: run inside WSL; ensure `libgmp-dev` is installed; reinstall `pgf` if needed.

### "Line endings / Syntax error near unexpected token"

* Cause: file saved with Windows CRLF.
* Fix:

  ```bash
  dos2unix <filename>
  ```

### "404 Not Found" on /generate

* Cause: hitting a non-versioned endpoint.
* Fix: use the `/api/v1` prefix (example below).

### "Tools run fails with invalid path / missing repo root"

* Cause: `FILESYSTEM_REPO_PATH` missing/incorrect or tool path resolves outside repo root.
* Fix: set `FILESYSTEM_REPO_PATH` to the repo root inside the backend runtime environment.

### "AI tool returns 403"

* Cause: AI tools are gated.
* Fix: set `ARCHITECT_ENABLE_AI_TOOLS=1` in the backend environment and restart.

---

## 9. Verification (Smoke Test)

Run in WSL to verify end-to-end generation.

### Test A: Standard BioFrame

```bash
curl -X POST "http://localhost:8000/api/v1/generate/en" \
     -H "Content-Type: application/json" \
     -d '{
           "frame_type": "bio",
           "name": "Alan Turing",
           "profession": "computer scientist",
           "nationality": "british",
           "gender": "m"
         }'
```

### Test B: Ninai Protocol

```bash
curl -X POST "http://localhost:8000/api/v1/generate/en" \
     -H "Content-Type: application/json" \
     -d '{
           "function": "ninai.constructors.Statement",
           "args": [
             { "function": "ninai.types.Bio" },
             { "function": "ninai.constructors.List", "args": ["physicist", "chemist"] }
           ]
         }'
```

Expected response shape (example):

```json
{
  "surface_text": "Alan Turing is a physicist and chemist.",
  "meta": {
    "engine": "WikiEng",
    "adapter": "NinaiAdapter",
    "strategy": "SimpNP"
  }
}
```
