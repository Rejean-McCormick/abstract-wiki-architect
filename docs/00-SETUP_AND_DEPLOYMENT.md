# 🛠️ Setup & Deployment Guide

**SemantiK Architect — current repository layout**

This guide covers installation, configuration, local development, and Docker deployment for the current repository.

Because the backend depends on **Grammatical Framework (GF)** and the Python `pgf` bindings, the backend must run in a **Linux environment**. On Windows, the recommended setup is hybrid:

1. **Windows 11**: editing, Git, frontend
2. **WSL 2 (Ubuntu)**: backend, Python environment, Redis, GF

---

## 1. Prerequisites

Recommended host setup:

- **Windows 10/11** with **WSL 2**
- **Ubuntu** installed in WSL
- **VS Code** with the **WSL** extension
- **Node.js 18+** on Windows for the frontend
- **Docker Desktop** if you want Redis via Docker and/or full-stack Docker deployment

Inside WSL, install the base Linux packages you need for Python builds and GF-related tooling:

```bash
sudo apt update
sudo apt install -y \
  python3-venv python3-dev \
  build-essential libgmp-dev \
  git curl wget dos2unix
````

> Keep the repository on your Windows drive if you want both Windows and WSL to share the same working tree.

---

## 2. Repository Layout

Use the repository root that contains `manage.py`, `pyproject.toml`, `requirements.txt`, `app/`, and `architect_frontend/`.

Recommended layout:

```text
C:\MyCode\SemantiK_Architect\
└── SemantiK_Architect\                 <-- repo root
    ├── .env
    ├── .venv/                          <-- local Python environment
    ├── manage.py
    ├── pyproject.toml
    ├── requirements.txt
    ├── app/
    ├── architect_frontend/
    ├── builder/
    ├── data/
    ├── docs/
    ├── gf/
    │   └── semantik_architect.pgf
    ├── gf-rgl/                         <-- clone or place gf-rgl here
    ├── schemas/
    └── tools/
```

In WSL, the same repo will usually be visible as:

```bash
/mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect
```

> `gf-rgl/` is expected inside the repo root for the current toolchain and Docker setup.

---

## 3. GF / RGL Setup (WSL)

Open a **WSL terminal** and go to the repo root:

```bash
cd /mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect
```

### A. Install GF

Install a GF package appropriate for your Ubuntu release, then verify:

```bash
gf --version
```

If `gf` is already available in your WSL environment, you can skip this step.

### B. Ensure `gf-rgl/` exists in the repo root

If `gf-rgl/` is not already present:

```bash
git clone https://github.com/GrammaticalFramework/gf-rgl.git
```

This should create:

```text
<repo-root>/gf-rgl/
```

---

## 4. Python Environment (WSL)

For the current repository state, keep local installation simple: **one Python environment at the repo root**.

Preferred:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Fallback if you are not using `uv`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> For now, install from `requirements.txt`. The repo also contains a `pyproject.toml`, but the current worker Docker image still installs from `requirements.txt`, so this is the least surprising local setup.

---

## 5. Environment Configuration (`.env`)

Create a `.env` file in the repo root.

**File:** `.env`

```ini
# --- App ---
APP_NAME=Semantik Architect
APP_ENV=development
DEBUG=true

# --- Repo / Filesystem ---
FILESYSTEM_REPO_PATH=/mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect

# --- GF / PGF ---
GF_LIB_PATH=/mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect/gf-rgl
PGF_PATH=/mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect/gf/semantik_architect.pgf

# Legacy compatibility only (optional)
AW_PGF_PATH=/mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect/gf/semantik_architect.pgf

# --- Redis / Worker ---
REDIS_URL=redis://localhost:6379/0
REDIS_QUEUE_NAME=architect_tasks

# --- Local browser dev ---
ARCHITECT_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# --- Optional: only set this when backend is mounted behind a reverse proxy ---
# ARCHITECT_API_ROOT_PATH=/semantik_architect

# --- Optional API auth ---
# API_KEY=change-me
# API_SECRET=change-me
```

Notes:

* Prefer **`PGF_PATH`**. `AW_PGF_PATH` is legacy compatibility.
* `FILESYSTEM_REPO_PATH` should point to the repo root visible from the backend runtime.
* `ARCHITECT_API_ROOT_PATH` is only needed when the backend is mounted behind a prefix such as `/semantik_architect`.

---

## 6. Local Development

There are three practical ways to run the stack.

### Option A — Windows launcher (recommended on Windows)

From **PowerShell** at the repo root:

```powershell
.\Run-Architect.ps1
```

What it does:

* starts the API in WSL
* starts the worker in WSL
* starts the frontend on Windows
* probes backend readiness
* opens the default tools UI URL

Useful flags:

```powershell
.\Run-Architect.ps1 -NoPortClear
.\Run-Architect.ps1 -EnableReload -EnableWatch
.\Run-Architect.ps1 -SkipFrontend
```

### Option B — Canonical CLI orchestrator (WSL)

From WSL at the repo root:

```bash
source .venv/bin/activate
python manage.py doctor
python manage.py start
```

Useful commands:

```bash
python manage.py build --align
python manage.py clean
python manage.py doctor
```

### Option C — Manual run (4 terminals)

#### Terminal 1 — Redis

With Docker:

```bash
docker run -p 6379:6379 --name aw_redis -d redis:alpine
```

#### Terminal 2 — API backend (WSL)

```bash
cd /mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect
source .venv/bin/activate
python -m uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

#### Terminal 3 — Async worker (WSL)

```bash
cd /mnt/c/MyCode/SemantiK_Architect/SemantiK_Architect
source .venv/bin/activate
python -m arq app.workers.worker.WorkerSettings --watch app
```

#### Terminal 4 — Frontend (Windows PowerShell)

```powershell
cd architect_frontend
npm install
npm run dev
```

### Local URLs

Frontend:

* `http://localhost:3000/semantik_architect`
* `http://localhost:3000/semantik_architect/dev`
* `http://localhost:3000/semantik_architect/tools`

Backend:

* `http://localhost:8000/docs`
* `http://localhost:8000/health/ready`
* `http://localhost:8000/api/v1/health/ready`

---

## 7. API Notes

Current backend behavior:

* Canonical API prefix: **`/api/v1`**
* Local dev frontend expects backend on `:8000`
* Local dev frontend origin `:3000` is allowed by default in development
* The generate endpoint is available at **`POST /api/v1/generate/{lang_code}`**
* A payload-based variant also exists at **`POST /api/v1/generate`**

For the safest smoke tests, use the language-path form:

```bash
curl -X POST "http://localhost:8000/api/v1/generate/en" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
        "frame_type": "bio",
        "subject": { "name": "Marie Curie", "qid": "Q7186" },
        "properties": { "label": "Marie Curie" }
      }'
```

If your local environment does **not** enforce API auth, you can omit `X-API-Key`.

Expected response shape:

```json
{
  "text": "…",
  "lang_code": "en"
}
```

---

## 8. Docker Deployment

The repo includes:

* `docker/Dockerfile.backend`
* `docker/Dockerfile.worker`
* `docker/Dockerfile.frontend`
* `docker-compose.yml`
* `deploy/nginx.conf`

### Full stack

Run from the repo root:

```bash
docker-compose up --build -d
```

### What starts

* `redis`
* `backend`
* `worker`
* `frontend`
* `nginx`

### Public URLs

The reverse proxy publishes the app here:

* `http://localhost:4000/semantik_architect/`
* `http://localhost:4000/semantik_architect/tools`
* `http://localhost:4000/semantik_architect/api/v1/...`

### Docker notes

* Inside containers, the repo is mounted at `/app`
* The frontend is served under `/semantik_architect`
* Nginx proxies `/semantik_architect/api/*` to the backend
* Docker currently uses:

  * backend on port `8000`
  * frontend on port `3000`
  * nginx on host port `4000`

---

## 9. Troubleshooting

### `pgf` module not found

Cause:

* backend running on Windows instead of Linux/WSL
* missing build prerequisites such as `libgmp-dev`

Fix:

```bash
sudo apt install -y libgmp-dev build-essential python3-dev
source .venv/bin/activate
pip install -r requirements.txt
```

### `gf-rgl/ folder missing`

Cause:

* repo root does not contain `gf-rgl/`

Fix:

```bash
cd <repo-root>
git clone https://github.com/GrammaticalFramework/gf-rgl.git
```

### Frontend says `Failed to fetch`

Cause:

* backend is not running
* CORS is misconfigured
* frontend is trying to hit the wrong API base

Fix:

* confirm backend on `http://localhost:8000`
* confirm `ARCHITECT_CORS_ORIGINS` includes `http://localhost:3000`
* confirm you are using the canonical `/api/v1` routes

### `404 Not Found` on the API

Cause:

* missing `/api/v1` prefix
* wrong base path under Docker/reverse proxy

Fix:

* local dev backend: use `/api/v1/...`
* behind Nginx: use `/semantik_architect/api/v1/...`

### Build artifacts end up in the wrong place

Cause:

* generated GF files or PGF are being written outside the expected repo locations

Fix:

* keep generated grammar artifacts under `gf/`
* keep `PGF_PATH` pointing to `gf/semantik_architect.pgf`

---

## 10. Verification Checklist

From WSL:

```bash
source .venv/bin/activate
python manage.py doctor
```

Then verify:

1. `gf --version` works
2. `gf-rgl/` exists at repo root
3. `gf/semantik_architect.pgf` exists after a build
4. `http://localhost:8000/api/v1/health/ready` returns 200
5. `http://localhost:3000/semantik_architect/tools` loads
6. `curl` to `/api/v1/generate/en` returns 200 or a clear auth/validation response

---

## 11. Minimal Day-to-Day Commands

### Start everything (Windows hybrid)

```powershell
.\Run-Architect.ps1
```

### Start everything from WSL

```bash
source .venv/bin/activate
python manage.py start
```

### Rebuild grammar layer

```bash
source .venv/bin/activate
python manage.py build --align
```

### Frontend only

```powershell
cd architect_frontend
npm run dev
```

### Backend only

```bash
source .venv/bin/activate
python -m uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```
