
# Developer Setup Guide (Hybrid Environment)

This project uses a **Hybrid Architecture**:

1. **Windows 11:** Source code editing (VS Code), git operations, and Docker Desktop.
2. **WSL 2 (Ubuntu):** Backend execution, Python environment, and Grammatical Framework (GF) compilation.

**CRITICAL NOTE:** Do not attempt to run the Python backend or GF compilation directly in Windows PowerShell. The required C-libraries (`pgf`) and the grammar binary format are Linux-native.

---

## 1. Prerequisites

* **Windows 10/11** with WSL 2 enabled.
* **Ubuntu 22.04 or 24.04** installed via Microsoft Store.
* **Docker Desktop** (configured to use the WSL 2 backend).
* **VS Code** with the **"WSL"** extension installed.

---

## 2. Directory Structure

The system expects the main grammar file (`Wiki.pgf`) to reside in a `gf/` folder within the repository, and the RGL to be a sibling directory.

**Required Layout:**

```text
/mnt/c/MyCode/AbstractWiki/
├── abstract-wiki-architect/      <-- This Repository
│   ├── .env                      <-- Configuration File
│   ├── gf/                       <-- Compiled Grammars Location
│   │   └── Wiki.pgf              <-- The Active Master Grammar
│   └── ...
└── gf-rgl/                       <-- GF Resource Grammar Library (Source)

```

---

## 3. System Initialization (WSL)

Open your **Ubuntu/WSL Terminal** (not PowerShell) and run these commands to install the core C-dependencies.

```bash
# 1. Update packages
sudo apt update

# 2. Install Python tools, C compiler, and GMP (Required for PGF runtime)
sudo apt install -y python3-venv python3-dev build-essential libgmp-dev

# 3. Install dos2unix (Crucial for fixing Windows line-ending issues in scripts)
sudo apt install -y dos2unix

# 4. Install the GF Compiler (Binary)
# (Assuming the .deb file is in your project root, otherwise download from GF website)
# wget [https://www.grammaticalframework.org/download/gf-3.12-ubuntu-22.04.deb](https://www.grammaticalframework.org/download/gf-3.12-ubuntu-22.04.deb)
sudo apt install ./gf-3.12-ubuntu-24.04.deb

# Verify installation
gf --version

```

---

## 4. Building the Resource Grammar Library (RGL)

*Note: This step is required for the "Full" compiler mode. For simple testing with `Wiki.pgf`, you can skip to Step 5.*

1. **Clone the RGL** (if missing):
```bash
cd /mnt/c/MyCode/AbstractWiki/
git clone [https://github.com/GrammaticalFramework/gf-rgl.git](https://github.com/GrammaticalFramework/gf-rgl.git)

```


2. **Fix Line Endings & Build**:
Windows git cloning often adds `CRLF` characters that break Linux build scripts.
```bash
cd gf-rgl
dos2unix Setup.sh languages.csv
chmod +x Setup.sh

# Build and Install (Takes ~5-10 minutes)
sudo ./Setup.sh

```



---

## 5. Python Environment Setup

Perform all these steps inside the `abstract-wiki-architect` folder in **WSL**.

```bash
cd /mnt/c/MyCode/AbstractWiki/abstract-wiki-architect

# 1. Create Virtual Env
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install Dependencies
# This installs FastAPI, Arq, and compiles the PGF C-extension locally
pip install -r requirements.txt

```

**Manual PGF Install (If requirements fail):**
If `pip install -r requirements.txt` fails on the `pgf` step, run this manually:

```bash
pip install pgf

```

---

## 6. Application Configuration

Create a file named **`.env`** in the project root (`abstract-wiki-architect/.env`). This bridges the Windows file path to the Linux app.

```ini
# .env
# --- Engine Configuration ---
USE_MOCK_GRAMMAR=False

# --- Persistence Paths ---
# Point to the folder containing 'Wiki.pgf'
FILESYSTEM_REPO_PATH=/mnt/c/MyCode/AbstractWiki/abstract-wiki-architect/gf

# --- Dependencies ---
GF_LIB_PATH=/mnt/c/MyCode/AbstractWiki/gf-rgl

# --- App Settings ---
APP_ENV=development
LOG_LEVEL=INFO
STORAGE_BACKEND=filesystem
API_SECRET=dev-secret-123

```

---

## 7. Running the Application

You need three terminal tabs (all in WSL).

### Terminal 1: Redis (Message Broker)

```bash
docker run -p 6379:6379 redis

```

### Terminal 2: The API Server

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

```

*Wait for the log: `gf_grammar_loaded .../gf/Wiki.pgf*`

### Terminal 3: The Background Worker

```bash
source venv/bin/activate
arq app.workers.worker.WorkerSettings

```

---

## 8. Verification (Smoke Test)

To confirm the engine is actually working, run this `curl` command (in WSL).
This uses the simple `Wiki.pgf` test grammar (John/Apple).

```bash
curl -X POST http://localhost:8000/api/v1/generate \
-H "Content-Type: application/json" \
-d '{
  "target_language": "kor", 
  "semantic_frame": {
    "frame_type": "John",
    "subject": {}, 
    "meta": {}
  }
}'

```

**Success Response:**

```json
{"text": "John", "lang_code": "kor", "debug_info": {...}}

```

