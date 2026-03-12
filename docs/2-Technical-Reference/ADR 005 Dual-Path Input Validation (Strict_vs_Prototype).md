# ADR 005: Dual-Path Input Validation (Strict vs. Prototype)

### 1. Context and Problem Statement

The SemantiK Architect operates in two distinct phases of the software lifecycle:

1. **Architecting (Draft Mode):** Developers and AI agents must invent new grammar functions (e.g., `mkIsAProperty`, `mkRobot`) rapidly to test linguistic theories.
2. **Publishing (Production Mode):** The system generates high-reliability content using agreed-upon standards and shared libraries.

**The Problem:** The system currently enforces **Ninai Protocol** validation globally. Ninai acts as a strict "bouncer," rejecting any function call that has not been pre-registered in its library. This creates a development bottleneck: to test a single line of new GF grammar, the developer must first fork, edit, and reinstall the Python validation library. This blocks the "Sketchy/Draft" phase of development.

### 2. The Decision

We are adopting a **Dual-Path Architecture** for the Generation API (`/generate`). The system will effectively "relax" the API contract to accept two distinct input schemas:

* **Path A: Strict Mode (The "Green" Path)**
* **Schema:** `ninai.constructors.Statement`
* **Behavior:** Validates inputs against the strict Ninai allowlist.
* **Target Audience:** Production services, Regression tests, Team interoperability.
* **Error Handling:** Fails *before* execution if the semantic frame is invalid.


* **Path B: Prototype Mode (The "Red" Path)**
* **Schema:** `UniversalNode` (Recursive Generic Object)
* **Behavior:** Accepts *any* function name and argument list. It acts as a transparent pass-through to the GF Compiler.
* **Target Audience:** The Architect Agent, Human Prototyping, AI Hallucinations.
* **Error Handling:** Fails *during* execution (Runtime Error) if the GF compiler rejects the function.



### 3. Architecture Diagram

**Flow Logic:**

1. **API Router:** Receives the JSON payload.
2. **Dispatcher:**
* Attempts to parse as **Strict Ninai**.
* If that fails (or if the structure explicitly matches the Generic schema), it falls back to **Prototype Mode**.


3. **Engine Adapter:** Uses "Duck Typing" (Dynamic Typing) to read the `.function` and `.args` attributes from *either* object type.
4. **GF Runtime:** Executes the command.

### 4. Technical Specification: The Universal Node

To support the Prototype Path, we define a recursive schema that mimics the *structure* of a syntax tree without enforcing the *content*.

**Schema Definition (JSON Semantic):**

```json
{
  "function": "String (Required) - The name of the GF operation",
  "args": [
    "String | Integer | Float",
    "OR Another UniversalNode Object (Recursive)"
  ]
}

```

**Example Payload (Prototype):**

```json
{
  "function": "mkIsAProperty",
  "args": [
    "Sky",
    {
      "function": "mkColor",
      "args": ["Blue"]
    }
  ]
}

```

### 5. Consequences

| **Positive** | **Negative** |
| --- | --- |
| **Velocity:** Developers can test new grammar functions immediately without touching Python code. | **Runtime Errors:** Typos (e.g., `mkBio` vs `mkBoi`) will not be caught until the GF binary actually tries to run, potentially causing obscure error messages from the C-runtime. |
| **AI Compatibility:** The "Architect Agent" (LLM) can hallucinate new grammar structures that validly execute, allowing for autonomous grammar discovery. | **Documentation Drift:** Since functions don't need to be registered, the API documentation (Swagger) won't automatically list all available grammar commands. |
| **Interoperability:** We maintain full compatibility with the Ninai standard for the wider team. |  |

### 6. Implementation Strategy

1. **Domain Layer:** Define the `UniversalNode` Pydantic model.
2. **API Layer:** Update `routes.py` to use `Union[Statement, UniversalNode]` for the request body.
3. **Adapter Layer:** Refactor `gf_wrapper.py` to serialize both object types into GF Linearize commands.

---

**Status:** `ACCEPTED`
**Date:** 2025-12-23
**Author:** SemantiK Architect Team