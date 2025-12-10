### The Linux Environment Solution (WSL)

You are using **WSL 2 (Windows Subsystem for Linux)** running an **Ubuntu** distribution.

  * **What it is:** It acts like a "Virtual Machine" integrated directly into Windows, but without the slowness or isolation of a traditional VM. It gives you a real Linux kernel and terminal command line.
  * **Why we need it:** Your project relies on the **Grammatical Framework (GF)** library (`pgf`). This library is built with C++ and is native to Linux. Installing it on Windows requires complex compiler setups (Visual Studio Build Tools) that often fail. In Linux (Ubuntu), we just ran `apt install build-essential` and it worked instantly.
  * **How it works:**
      * Your code lives on your Windows hard drive (`C:\MyCode\...`).
      * WSL "mounts" your C: drive so Linux can see it at `/mnt/c/`.
      * You edit files in Windows (VS Code, Notepad, etc.).
      * You **run** the backend in the Linux terminal because that's where the Python environment with the compiled C++ libraries lives.

-----

### 📝 Context to Carry Forward (Copy-Paste this for your next chat)

When you start a new conversation, paste this block so the AI knows exactly where you stand:

> **Project Context: Abstract Wiki Architect**
>
> **1. Environment Setup (Hybrid):**
>
>   * **OS:** Windows 11 with **WSL 2 (Ubuntu)** installed.
>   * **Code Location:** `C:\MyCode\AbstractWiki\abstract-wiki-architect` (mapped to `/mnt/c/...` in WSL).
>   * **Backend:** Runs inside **WSL** (Ubuntu) to support the `pgf` C++ library.
>       * *Command:* `source venv/bin/activate` -\> `uvicorn architect_http_api.main:app --reload --port 8000 --host 0.0.0.0`
>   * **Frontend:** Runs in **Windows PowerShell** (standard Next.js).
>       * *Command:* `npm run dev` (Port 3000).
>
> **2. Current Code State:**
>
>   * **GF Engine:** The file `architect_http_api/gf/__init__.py` is set to **load** the real engine (we reverted the "disable" patch).
>   * **Dependencies:** `pgf` and `google-generativeai` are installed in the WSL `venv`.
>   * **Configuration:** `language_profiles/profiles.json` uses **3-letter ISO codes** (e.g., `fra`, `eng`) to match the API.
>   * **Lexicons:** We have a script `utils/seed_lexicon_ai.py` to generate dictionaries using Gemini, bypassing the need for the full RGL build pipeline if necessary.
>
> **3. Immediate Goal:**
>
>   * We are verifying that the backend (in WSL) correctly generates text using the Python engines (Romance, Germanic) and the GF engine.

-----

### How to Resume Work Next Time

**1. Start the Frontend (Windows Terminal)**

```powershell
cd C:\MyCode\AbstractWiki\abstract-wiki-architect\architect_frontend
npm run dev
```

**2. Start the Backend (Ubuntu/WSL Terminal)**

```bash
# Enter Linux
wsl

# Go to project (Windows C: is /mnt/c in Linux)
cd /mnt/c/MyCode/AbstractWiki/abstract-wiki-architect

# Activate Python Virtual Env
source venv/bin/activate

# Run Server
uvicorn architect_http_api.main:app --reload --port 8000 --host 0.0.0.0
```