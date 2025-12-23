
# 🛠️ Setup & Deployment Guide

**Abstract Wiki Architect**

This guide covers the installation, configuration, and deployment of the Abstract Wiki Architect. Because the core engine depends on the **Grammatical Framework (GF)** C-libraries (`libpgf`), the backend **must run in a Linux environment**.

For developers on Windows, we utilize a **Hybrid Architecture**:

1. **Windows 11:** Source code editing (VS Code), Git operations, Frontend execution.
2. **WSL 2 (Ubuntu):** Backend execution, Python environment, and GF compilation.

---

## 1. Prerequisites

Before starting, ensure you have the following installed:

* **Windows 10/11** with **WSL 2** enabled.
* **Ubuntu 22.04 LTS** (or newer) installed from the Microsoft Store.
* **Docker Desktop** (configured to use the WSL 2 backend).
* **VS Code** with the **"WSL"** extension installed.
* **Node.js 18+** (Installed on Windows for the Frontend).

---

## 2. Directory Structure & Pathing

To prevent "Path not found" errors, you must understand the mapping between Windows and Linux.

* **Windows Path:** `C:\MyCode\AbstractWiki\`
* **WSL Path:** `/mnt/c/MyCode/AbstractWiki/`

**Recommended Layout:**

```text
/mnt/c/MyCode/AbstractWiki/
├── abstract-wiki-architect/      <-- [REPO ROOT] This repository
│   ├── .env                      <-- Env variables (Shared)
│   ├── gf/                       <-- Compilation Artifacts
│   │   └── AbstractWiki.pgf      <-- The Binary (Generated)
│   ├── docker/                   <-- Container configurations
│   └── ...
└── gf-rgl/                       <-- [EXTERNAL] GF Resource Grammar Library
    └── src/                      <-- RGL Source files (French, English, etc.)

```

> **⚠️ CRITICAL:** Do not clone the repo into the Linux native filesystem (`~/home/user/`) if you plan to edit files in Windows. Clone it to your `C:` drive so both OSs can access it.

---

## 3. System Initialization (WSL Side)

Open your **Ubuntu/WSL Terminal** (NOT PowerShell) and navigate to the project root:

```bash
cd /mnt/c/MyCode/AbstractWiki/abstract-wiki-architect

```

### Step A: Install C-Library Dependencies

The GF runtime requires specific C libraries to compile bindings.

```bash
# 1. Update package lists
sudo apt update

# 2. Install Python dev tools, C compilers, and GMP (Math library for PGF)
sudo apt install -y python3-venv python3-dev build-essential libgmp-dev

# 3. Install dos2unix (Critical for fixing Windows line-ending corruptions)
sudo apt install -y dos2unix

```

### Step B: Install the GF Compiler

You need the `gf` binary to compile grammar files.

```bash
# Download the Debian package (Check GF website for latest version)
wget https://www.grammaticalframework.org/download/gf-3.12-ubuntu-22.04.deb

# Install
sudo apt install ./gf-3.12-ubuntu-22.04.deb

# Verify
gf --version
# Output should be: Grammatical Framework (GF) version 3.12

```

### Step C: Setup the Resource Grammar Library (RGL)

The system needs the RGL source code to build Tier 1 languages.

```bash
# 1. Go to the parent directory
cd .. 

# 2. Clone the RGL
git clone https://github.com/GrammaticalFramework/gf-rgl.git

# 3. Fix Line Endings (CRLF -> LF)
# Windows git often corrupts shell scripts. We must fix them.
cd gf-rgl
dos2unix Setup.sh
chmod +x Setup.sh

# 4. Build and Install the RGL (Takes ~5 minutes)
sudo ./Setup.sh

```

---

## 4. Python Environment (WSL Side)

Perform these steps inside `abstract-wiki-architect`.

```bash
# 1. Create Virtual Environment
python3 -m venv venv

# 2. Activate (Do this every time you open a terminal)
source venv/bin/activate

# 3. Install Dependencies
# This compiles the 'pgf' C-extension locally. If this fails, check Step A.
pip install -r requirements.txt

```

---

## 5. Configuration (`.env`)

Create a `.env` file in the project root. This configures the paths and services.

**File:** `.env`

```ini
# --- Application Meta ---
APP_NAME=abstract-wiki-architect
APP_ENV=development
DEBUG=true
LOG_LEVEL=INFO
LOG_FORMAT=console

# --- Persistence (Hexagonal Ports) ---
# In Hybrid Mode, this points to your mapped C: drive location
FILESYSTEM_REPO_PATH=/mnt/c/MyCode/AbstractWiki/abstract-wiki-architect

# --- Grammar Engine ---
# Points to the sibling directory we cloned in Step 3
GF_LIB_PATH=/mnt/c/MyCode/AbstractWiki/gf-rgl

# --- Messaging (Redis) ---
# When running locally with Docker Redis, use localhost
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_QUEUE_NAME=architect_tasks

# --- Worker ---
WORKER_CONCURRENCY=2

# --- Optional: AI Services ---
# GOOGLE_API_KEY=your-gemini-key

```

---

## 6. Running Locally (Hybrid Mode)

You will need **4 Terminal Tabs**.

### Terminal 1: Message Broker (Powershell or WSL)

We use Docker just for Redis, as installing Redis on Windows is messy.

```powershell
docker run -p 6379:6379 --name aw_redis -d redis:alpine

```

### Terminal 2: API Backend (WSL)

Hosts the FastAPI server.

```bash
# Activate Env
source venv/bin/activate

# Run Server (Hot Reload Enabled)
uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

```

*Wait for log: `Application startup complete.*`

### Terminal 3: Async Worker (WSL)

Processes background compilations.

```bash
# Activate Env
source venv/bin/activate

# Run Arq Worker (Watch Mode Enabled for Hot Reload)
arq app.workers.worker.WorkerSettings --watch app

```

*Wait for log: `worker_startup*`

### Terminal 4: Frontend (Windows PowerShell)

The UI doesn't need Linux, so run it natively for better browser performance.

```powershell
cd architect_frontend
npm install
npm run dev

```

*Access UI at: `http://localhost:3000*`

---

## 7. Production Deployment (Docker)

For production or full-stack testing, use `docker-compose`. This runs everything (Backend, Worker, Redis, Frontend) in isolated containers.

### Key differences in Docker

* **Pathing:** The `docker-compose.yml` mounts the root directory to `/app`.
* **Networking:** Services talk via hostname (`redis`, `backend`), not `localhost`.

### 1. Build and Run

```bash
# Build images and start services
docker-compose up --build -d

```

### 2. Verify Services

```bash
docker-compose ps

```

You should see:

* `aw_backend`: Port 8000
* `aw_worker`: Up
* `aw_redis`: Port 6379
* `aw_frontend`: Port 3000

### 3. Trigger a Rebuild (Manual)

If you change code, you usually just need to restart the specific container due to volume mounting.

```bash
docker-compose restart backend worker

```

---

## 8. Troubleshooting

### "pgf module not found"

* **Cause:** You tried to run python from Windows PowerShell, or `pip install` failed to compile the C extension.
* **Fix:** Ensure you are in **WSL**. Run `sudo apt install libgmp-dev` and try `pip install --force-reinstall pgf`.

### "Line endings / Syntax error near unexpected token"

* **Cause:** A script (`Setup.sh` or `build_orchestrator.py`) was saved with Windows `CRLF` line endings.
* **Fix:** Run `dos2unix <filename>` on the offending script.

### "Redis Connection Refused"

* **Context:** Running **Hybrid Mode**.
* **Fix:** Ensure `REDIS_HOST=localhost` in `.env`.
* **Context:** Running **Docker Mode**.
* **Fix:** Ensure `REDIS_HOST=redis` (the service name). The `docker-compose.yml` handles this automatically via environment overrides.

### "Last Man Standing" / PGF only has one language

* **Cause:** You are using the old build loop.
* **Fix:** Ensure you are using the updated `build_orchestrator.py` which implements the **Two-Phase Build (Verify -> Link)**.

### "Worker not picking up new grammar"

* **Cause:** The worker loads the PGF into RAM on startup.
* **Fix:** The updated `worker.py` has a file watcher. Ensure the `backend` and `worker` share the same volume (`/app`) in `docker-compose.yml`. Check worker logs for `watcher_triggering_reload`.

---

## 9. Verification (Smoke Test)

Run this command (in WSL) to verify the engine is generating text:

```bash
curl -X POST "http://localhost:8000/api/v1/generate?lang=eng" \
     -H "Content-Type: application/json" \
     -d '{
           "frame_type": "bio",
           "name": "Alan Turing",
           "profession": "computer_scientist",
           "nationality": "british"
         }'

```

**Expected JSON Response:**

```json
{
  "result": "Alan Turing is a British computer scientist.",
  "meta": { "engine": "WikiEng", "latency": "..." }
}

```