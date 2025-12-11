The current AI landscape in your project is fragmented across `utils/` and `builder/`. To add the new "Judge" and "Gold Generator" capabilities effectively, we need to consolidate these into a unified **AI Services Layer**.

Here is the comprehensive documentation and implementation plan for the **Abstract Wiki AI Architecture**.

-----

# 🤖 Abstract Wiki AI Architecture

This document defines how Artificial Intelligence (Gemini) is integrated into the Abstract Wiki Architect to automate lexicon creation, grammar repair, and quality assurance.

## 1\. The Three AI Personas

We consolidate all AI logic into three distinct "Agents" or modules, each with a specific responsibility.

| Agent | Role | Current Script | Responsibility |
| :--- | :--- | :--- | :--- |
| **The Lexicographer** | Data Generator | `utils/seed_lexicon_ai.py` | Generates dictionary words (`apple_N`, `walk_V`) and their morphological classes for new languages. |
| **The Surgeon** | Code Fixer | `builder/architect_ai.py` | Reads compiler error logs and surgically repairs broken `.gf` source code (The "Self-Healing" pipeline). |
| **The Judge** | QA & Validation | **[NEW]** | Generates Gold Reference sentences and evaluates if the GF engine's output is linguistically correct. |

-----

## 2\. Directory Structure (Consolidated)

We will move scattered scripts into a central package `ai_services/`.

```text
ai_services/
├── __init__.py           # Exposes the 3 agents to the rest of the app
├── client.py             # Central Gemini setup, API keys, and Rate Limiting
├── lexicographer.py      # Lexicon generation logic
├── surgeon.py            # Grammar repair logic (was architect_ai.py)
└── judge.py              # [NEW] Validation & Gold Standard generation
```

-----

## 3\. Implementation: The Judge (`ai_services/judge.py`)

This new module fulfills your requirement: generating gold data and validating engine output.

**Features:**

1.  **Gold Standard Generation:** Takes an Abstract Syntax Tree (AST) like `mkCl (mkN "cat") (mkV "eat")` and asks Gemini: *"How do you say 'The cat eats' in Amharic?"*
2.  **AI Validation:** Takes the GF output and asks Gemini: *"I have the sentence 'Le chat mange'. Is this a correct French translation for 'The cat eats'? Rate it 0-10."*

### Code for `ai_services/judge.py`

```python
import json
from . import client

def generate_gold_standard(concepts, lang_name):
    """
    Generates reference sentences for a list of concepts.
    concepts: List of English sentences or Abstract Trees (e.g. ["The cat walks", "John sleeps"])
    lang_name: Target language (e.g. "Amharic")
    """
    prompt = f"""
    Translate the following sentences into {lang_name}.
    Ensure the translation is natural but strictly grammatical.
    Return ONLY a JSON list of strings.
    
    Input: {json.dumps(concepts)}
    """
    
    response = client.generate(prompt)
    try:
        return json.loads(response)
    except:
        return []

def evaluate_output(source_concept, generated_text, lang_name):
    """
    Asks AI to judge the quality of the GF output.
    """
    prompt = f"""
    You are a linguistic judge.
    
    Task: Verify a translation.
    Source Concept: "{source_concept}" (English reference)
    Target Language: {lang_name}
    Generated Text: "{generated_text}"
    
    1. Is the generated text grammatically correct? (Yes/No)
    2. Does it preserve the meaning? (Yes/No)
    3. If No, provide the correct form.
    
    Return JSON: {{ "valid": bool, "score": 0-10, "correction": "..." }}
    """
    
    response = client.generate(prompt)
    try:
        return json.loads(response)
    except:
        return {"valid": False, "score": 0, "error": "AI parse failed"}
```

-----

## 4\. Implementation: The Client (`ai_services/client.py`)

This handles the connection, preventing you from writing `genai.configure` in every file.

```python
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
    # Using 'gemini-1.5-pro' for complex tasks, 'gemini-1.5-flash' for speed
    model = genai.GenerativeModel('gemini-1.5-pro') 

def generate(prompt):
    if not API_KEY:
        print("❌ AI Error: No API Key")
        return ""
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"❌ AI Exception: {e}")
        return ""
```

-----

## 5\. Workflow Integration

### A. Generating Gold Standards (Offline)

Run a script to populate your `tests/gold_standards/{lang}.json`.

```python
# tools/generate_gold.py
from ai_services import judge

test_sentences = ["The cat eats", "John walks", "The apple is red"]
gold_data = judge.generate_gold_standard(test_sentences, "Amharic")

# Save to file...
```

### B. Validating the Pipeline (Online/CI)

When `test_gf_dynamic.py` runs, it can now optionally call the Judge.

```python
# test_gf_dynamic.py update
from ai_services import judge

# ... after generating text ...
if USE_AI_VALIDATION:
    verdict = judge.evaluate_output("The cat eats", generated_text, "French")
    if verdict['valid']:
        print(f"✅ AI Approved: {generated_text}")
    else:
        print(f"⚠️ AI Suggestion: {verdict['correction']}")
```

-----

## 6\. Next Steps for You

1.  **Create the Folder:** `mkdir ai_services`
2.  **Move & Refactor:**
      * Move `utils/seed_lexicon_ai.py` logic -\> `ai_services/lexicographer.py`
      * Move `builder/architect_ai.py` logic -\> `ai_services/surgeon.py`
3.  **Create New Files:** Copy the code above for `client.py` and `judge.py`.
4.  **Update Imports:** Fix `build_orchestrator.py` to import `ai_services.surgeon` instead of `builder.architect_ai`.

This gives you a clean, documented, and scalable AI infrastructure.



Here is the consolidated reference list for your AI integration.

### 1. Configuration & Settings
* **Environment Variable:** `GOOGLE_API_KEY` (Required in `.env` file)
* **Model Selection:** Currently hardcoded as `gemini-1.5-pro` in `ai_services/client.py`.
* **Failure Report Path:** `data/reports/build_failures.json` (The shared memory between Compiler and Surgeon).

### 2. Core Modules (The `ai_services` Package)

#### **A. The Client (Infrastructure)**
* **Entry Point:** `ai_services/client.py`
* **Key Elements:**
    * `get_model()`: Lazy-loads the Gemini connection.
    * `generate(prompt)`: The universal wrapper for sending prompts and handling rate limits/errors.

#### **B. The Surgeon (Code Repair)**
* **Entry Point:** `ai_services/surgeon.py`
* **Key Elements:**
    * `repair_grammar(rgl_code, file_content, error_log)`: Accepts broken source code and compiler logs; returns fixed GF code strings.

#### **C. The Judge (QA & Validation)**
* **Entry Point:** `ai_services/judge.py`
* **Key Elements:**
    * `generate_gold_standard(concepts, lang_name)`: Creates reference translations for testing.
    * `evaluate_output(source_concept, generated_text, lang_name)`: Returns a JSON score (0-10) and correction for generated text.

#### **D. The Lexicographer (Data Generation)**
* **Entry Point:** `ai_services/lexicographer.py`
* **Key Elements:**
    * `generate_lexicon(words, lang_name)`: Returns morphological dictionaries (e.g., gender, plural forms) for new languages.

### 3. Pipeline Integration Points

#### **A. Build Orchestrator**
* **File:** `build_orchestrator.py`
* **Hook:** `healer.run_healing_round()`
* **Function:** Called immediately after a failed compilation attempt to trigger the Surgeon.

#### **B. The Healer (Bridge)**
* **File:** `builder/healer.py`
* **Function:** `run_healing_round()`
* **Role:** Reads `build_failures.json`, loops through errors, calls `surgeon.repair_grammar`, and overwrites files in `gf/`.

#### **C. Dynamic Tester**
* **File:** `test_gf_dynamic.py`
* **Hook:** `judge.evaluate_output()`
* **Function:** Called during runtime testing to verify if the output text (e.g., "The cat eats") is valid in the target language.