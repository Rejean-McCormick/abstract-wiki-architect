## 17. Setup

This page explains how to get **SemantiK Architect** running locally (for development) and how to deploy it (for production). The system’s backend runtime depends on **GF C-libraries**, so it must run in a **Linux environment**; on Windows, the recommended approach is a **Windows + WSL2 hybrid** (Windows for editing/frontend, WSL2 for backend + GF). 

### Supported development setup (recommended)

* **Windows 10/11 + WSL2 (Ubuntu)**: edit code and run the frontend on Windows, run backend services and GF tooling in WSL2. 
* Keep the repo on the **Windows drive** so both Windows and WSL can access the same working tree; avoid cloning into the Linux-only filesystem if you edit in Windows. 

### Prerequisites (high level)

You’ll need:

* WSL2 + Ubuntu (22.04+ suggested in the docs)
* Docker Desktop (WSL2 backend enabled)
* VS Code with the WSL extension
* Node.js 18+ (for the frontend) 

### Core setup steps (conceptual)

1. **System initialization (Linux side):** install OS build dependencies and the GF toolchain, and obtain the GF Resource Grammar Library (RGL). 
2. **Python environment (Linux side):** create a virtual environment and install Python dependencies. 
3. **Configuration:** create a `.env` at repo root to point the backend to repo paths, GF/RGL paths, compiled grammar artifact path, Redis, and tool limits. AI-related tools are explicitly gated by an environment flag. 

### Running locally

The docs describe two ways:

* **Unified launcher (recommended):** one entry point that starts API, worker, and frontend. 
* **Manual mode:** run Redis, the API backend, the worker, and the frontend as separate processes. 

The UI is served under a **base path** (not at the root), and there are dedicated dev/tools pages. 

### Production deployment (Docker)

For production/full-stack container runs, the docs use `docker-compose`. Key conceptual differences vs local:

* repo path is mounted into containers
* services talk via container hostnames (not `localhost`)
* UI and API are served under the configured base path and versioned API prefix 

### Troubleshooting (common themes)

* Backend errors about **pgf/lib** typically mean you’re running outside the Linux environment or missing system deps. 
* Windows/WSL file **line endings** can break scripts; convert when needed. 
* API calls should use the **versioned `/api/v1` prefix**. 
* Tool execution failures usually come from an incorrect repo-root path configuration. 
* AI tools may return authorization/gating errors if they’re disabled in configuration. 

### Verification (smoke test)

The docs include two end-to-end checks:

* a **standard structured frame** generation request
* a **Ninai protocol** generation request 
