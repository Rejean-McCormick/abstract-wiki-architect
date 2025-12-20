Here is the comprehensive documentation file. Create a file named **`DEVELOPER_SETUP.md`** in the root of your `abstract-wiki-architect` repository.

This covers the "Hybrid" Windows/WSL architecture we successfully established.

---

# Developer Setup Guide (Hybrid Environment)

This project uses a **Hybrid Architecture**:

1. **Windows 11:** Source code editing (VS Code), git operations, and Docker Desktop.
2. **WSL 2 (Ubuntu):** Backend execution, Python environment, and Grammatical Framework (GF) compilation.

**Note:** Do not attempt to run the Python backend or GF compilation directly in Windows PowerShell. The required C-libraries (`pgf`) are Linux-native.

## 1. Prerequisites

* **Windows 10/11** with WSL 2 enabled.
* **Ubuntu 22.04 or 24.04** installed from the Microsoft Store.
* **Docker Desktop** (configured to use the WSL 2 backend).
* **VS Code** with the "WSL" extension installed.

## 2. Directory Structure

We expect the GF Resource Grammar Library (RGL) to sit alongside this repository.

**Recommended layout:**

```text
/mnt/c/MyCode/AbstractWiki/
├── abstract-wiki-architect/  <-- This Repository
└── gf-rgl/                   <-- GF Resource Grammar Library (Source)

```

## 3. System Initialization (WSL)

Open your **Ubuntu/WSL Terminal** and install the necessary system tools.

```bash
# 1. Update packages
sudo apt update

# 2. Install Python build tools and C compiler (Required for PGF)
sudo apt install -y python3-venv python3-dev build-essential

# 3. Install dos2unix (Required to fix Windows line-endings in scripts)
sudo apt install -y dos2unix

# 4. Install the GF Compiler
# Download the deb package (check for latest version if needed)
wget https://www.grammaticalframework.org/download/gf-3.12-ubuntu-22.04.deb
sudo apt install ./gf-3.12-ubuntu-22.04.deb

# Verify installation
gf --version

```

## 4. Building the Resource Grammar Library (RGL)

The application needs the standard RGL compiled and installed in the system path.

1. **Clone the RGL** (if you haven't already):
```bash
cd /mnt/c/MyCode/AbstractWiki/
git clone https://github.com/GrammaticalFramework/gf-rgl.git

```


2. **Fix Line Endings & Build**:
Since we cloned on Windows, the scripts have `CRLF` endings which break Linux execution.
```bash
cd gf-rgl

# Convert script format to Unix
dos2unix Setup.sh languages.csv
chmod +x Setup.sh

# Build and Install (This takes ~5-10 minutes)
sudo ./Setup.sh

```



## 5. Python Environment Setup

Set up the virtual environment inside the repo folder **using WSL**.

```bash
cd /mnt/c/MyCode/AbstractWiki/abstract-wiki-architect

# 1. Create Virtual Env
python3 -m venv venv

# 2. Activate it
source venv/bin/activate

# 3. Upgrade pip (prevents binary compatibility issues)
pip install --upgrade pip

# 4. Install Dependencies
# This includes FastAPI, Arq, and compiles the PGF C-extension
pip install -r requirements.txt

```

**Verification:**
Run this command to ensure `pgf` is working:

```bash
python3 -c "import pgf; print(pgf.readPGF('/usr/local/lib/gf/prelude/Prelude.pgf'))"
# Output should be: <pgf.PGF object at ...>

```

## 6. Running the Application

You need three terminal tabs (all in WSL).

**Terminal 1: Redis (Message Broker)**
The simplest way is via Docker:

```bash
docker run -p 6379:6379 redis

```

**Terminal 2: The API Server**

```bash
source venv/bin/activate
uvicorn app.main:app --reload

```

*API is now available at http://localhost:8000*

**Terminal 3: The Worker (Compiler Service)**

```bash
source venv/bin/activate
arq app.workers.worker.WorkerSettings

```

## 7. Troubleshooting

**Error: `externally-managed-environment**`

* **Cause:** You are trying to `pip install` globally in Ubuntu.
* **Fix:** Ensure you created and activated the venv (`source venv/bin/activate`).

**Error: `./Setup.sh: required file not found**`

* **Cause:** The file has Windows line endings (`CRLF`).
* **Fix:** Run `dos2unix Setup.sh`.

**Error: `fatal error: gu/mem.h: No such file**`

* **Cause:** You are missing the GF C-runtime headers or `build-essential`.
* **Fix:** Ensure you ran `sudo apt install ./gf-3.12...` and `sudo apt install build-essential`.