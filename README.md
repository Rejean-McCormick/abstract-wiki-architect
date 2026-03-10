# Semantik Architect

**Industrial-grade NLG system for Abstract Wikipedia, Wikifunctions, and standalone API use.**

Semantik Architect is a data-driven Natural Language Generation (NLG) system built around a modular Python backend, GF-based grammar assets, language-specific schema/config data, and a separate Next.js frontend.

Instead of maintaining one monolithic renderer per language, the project combines:

- **A modular Python backend** for API, orchestration, persistence, and generation
- **GF grammars and PGF artifacts** for high-precision generation
- **Family-oriented engines and morphology modules** for rule-based text realization
- **Frame schemas and structured payloads** for language-agnostic input
- **A background worker** for long-running build and onboarding tasks
- **A separate frontend** for tools, dashboards, and operator workflows

The result is a practical architecture for rule-based NLG that can run as a standalone service while staying aligned with the broader Abstract Wikipedia workflow.

---

## Architecture Overview

Semantik Architect is best understood as a **modular monolith** on the Python side, with a **separate frontend application**.

```text
SemantiK_Architect/
├── app/                       # Python backend
│   ├── core/                 # Domain logic, constructions, ports, use cases
│   ├── adapters/             # API, worker, engines, persistence, messaging
│   └── shared/               # Config, DI container, observability, utilities
│
├── architect_frontend/       # Next.js frontend
├── gf/                       # GF source grammars and compiled artifacts
├── schemas/                  # JSON schemas for frame payloads
├── tools/                    # Diagnostics, audits, QA, indexing, health tools
├── builder/                  # Grammar/build orchestration
├── ai_services/              # Optional AI-assisted services
└── docs/                     # Architecture and operational documentation
````

### Backend responsibilities

* **`app/core/`** contains the domain model, semantic constructions, ports, and use cases
* **`app/adapters/`** contains FastAPI routes, generation engines, repositories, and infrastructure adapters
* **`app/shared/`** contains configuration, dependency injection, logging, and observability helpers

### Frontend responsibilities

* **`architect_frontend/`** is a separate Node/Next.js application
* It talks to the backend through the canonical API under **`/api/v1`**
* In local development it usually runs on **`:3000`**, while the backend runs on **`:8000`**

### Runtime topology

In containerized mode, the stack is split into:

* **Redis**
* **API backend**
* **ARQ worker**
* **Next.js frontend**
* **Nginx reverse proxy**

The reverse proxy exposes the app under:

* **UI:** `/semantik_architect/`
* **API:** `/semantik_architect/api/v1`

---

## Core Concepts

### 1. Semantic Frames

Semantic frames are the language-agnostic inputs to the generator. They describe *what* should be said before any language-specific realization happens.

Examples include:

* biographical facts
* entity descriptions
* relational/classification payloads
* event payloads

Example:

```json
{
  "frame_type": "bio",
  "subject": { "name": "Marie Curie", "qid": "Q7186" },
  "properties": {
    "profession": "physicist",
    "nationality": "polish"
  }
}
```

### 2. Constructions

The backend contains reusable constructions for common meaning patterns, such as:

* copular classification
* transitive events
* passive events
* topic-comment structures
* relative clauses
* possession and existential forms

These constructions let the system stay semantic-first rather than language-script-first.

### 3. Generation Engines

Semantik Architect supports multiple realization strategies:

* **GF-backed generation** for higher-precision, grammar-driven output
* **Python family/morphology engines** for rule-based realization paths and fallback strategies

### 4. Schemas and Configuration

The repository includes a dedicated `schemas/` directory with JSON Schemas for structured frame payloads. These schemas are separate from the Python packaging layer and act as contracts for incoming content and tooling.

### 5. Background Work

Long-running operations such as onboarding or building language resources are handled asynchronously through the worker stack rather than blocking the API process.

---

## Quick Start (Docker)

The easiest way to run the full stack is Docker Compose.

### Start everything

```bash
docker compose up --build
```

### Main endpoints

* **Reverse-proxied UI:** `http://localhost:4000/semantik_architect/`
* **Backend docs:** `http://localhost:8000/docs`
* **Direct frontend container port:** `http://localhost:3000`
* **Redis:** `localhost:6379`

### Health check

```bash
curl http://localhost:8000/api/v1/health/ready
```

You can also use the direct health route outside the API prefix:

```bash
curl http://localhost:8000/health/ready
```

---

## API Usage

The canonical backend contract lives under **`/api/v1`**.

### Generate text

Path-style language selection:

```bash
curl -X POST http://localhost:8000/api/v1/generate/eng \
  -H "x-api-key: secret" \
  -H "Content-Type: application/json" \
  -d '{
    "frame_type": "bio",
    "subject": {"name": "Marie Curie"},
    "properties": {"profession": "physicist", "nationality": "polish"}
  }'
```

There is also a payload-driven generation route for clients that send language inside the request body.

### Supported languages

```bash
curl http://localhost:8000/api/v1/languages
```

### Onboard or manage languages

Administrative language lifecycle operations live under the management layer and are intended to be protected.

Example:

```bash
curl -X POST http://localhost:8000/api/v1/languages/ \
  -H "x-api-key: secret" \
  -H "Content-Type: application/json" \
  -d '{"code": "zul", "name": "Zulu", "family": "Bantu"}'
```

---

## Local Development

### Recommended mental model

Keep local development simple:

* **one Python environment at the repo root**
* **one Node environment in `architect_frontend/`**

Do **not** create a separate Python virtual environment for every subdirectory unless you intentionally refactor the repo into multiple installable Python packages.

### Backend setup

Run the backend in **WSL/Linux or Docker**. The GF runtime and related dependencies are not a good fit for native Windows execution.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend setup

```bash
cd architect_frontend
npm install
npm run dev
```

### Run services manually

Backend:

```bash
source .venv/bin/activate
uvicorn app.adapters.api.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

Worker:

```bash
source .venv/bin/activate
arq app.workers.worker.WorkerSettings --watch app
```

Frontend:

```bash
cd architect_frontend
npm run dev
```

### Unified orchestration

For lifecycle operations such as build, doctor, align, and service startup, **`manage.py`** is the canonical orchestrator.

Examples:

```bash
python manage.py doctor
python manage.py align --force
python manage.py build --langs en fr
```

---

## Testing

The test suite is organized into:

* **unit** tests for core/domain behavior
* **integration** tests for adapters and infrastructure-aware flows
* **e2e** tests for API behavior

Typical commands:

```bash
pytest
pytest tests/unit
pytest tests/integration
```

---

## Build and Grammar Layer

Semantik Architect includes a GF build/orchestration pipeline and a compiled PGF runtime artifact.

Important directories:

* `gf/` for grammar sources and compiled output
* `builder/` for build orchestration
* `tools/` for audits, inventory, diagnostics, and health checks

If you are working on the grammar layer, prefer the documented build flow through `manage.py` and the builder/orchestrator tooling rather than ad hoc commands.

---

## Tools and Operator Workflows

The backend also exposes a protected **Tools API** used by the frontend dashboard.

This layer is designed around:

* an allowlisted registry of tool commands
* repo-root path confinement
* argument allowlisting
* output truncation and timeouts
* optional AI-gated tools

This keeps operational tooling usable from the UI without turning the backend into a generic remote shell.

---

## Status

Current repository direction:

* canonical FastAPI backend under **`app/adapters/api/main.py`**
* canonical API contract under **`/api/v1`**
* separate Next.js frontend under **`architect_frontend/`**
* async worker for background processing
* Dockerized multi-service deployment
* schema-driven input contracts
* observability hooks for structured logging and tracing

---

## Repository Map

* **Backend:** `app/`
* **Frontend:** `architect_frontend/`
* **Grammars:** `gf/`
* **Schemas:** `schemas/`
* **Operational tools:** `tools/`
* **Build orchestration:** `builder/`
* **AI helpers:** `ai_services/`
* **Docs:** `docs/`

---

## Links

* **Repository:** `README.md`, `docs/`, and the Docker files in this repo are the best current source of truth
* **Setup guide:** `docs/00-SETUP_AND_DEPLOYMENT.md`
* **Tools inventory:** `docs/17-TOOLS_AND_TESTS_INVENTORY.md`
* **API/UI unification notes:** `docs/APIUI Unification Update.txt`

