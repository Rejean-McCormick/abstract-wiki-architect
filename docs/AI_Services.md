= Abstract Wiki Architect: AI Services =

This document defines the integrated Artificial Intelligence layer of the Abstract Wiki Architect. The system consolidates all AI interactions into a unified `ai_services` package, using Large Language Models (Gemini) to handle tasks requiring semantic understanding, code repair, and linguistic quality assurance.

== The Three AI Personas ==

The architecture delegates responsibilities to three distinct AI agents, each serving a specific phase of the natural language generation pipeline.

{| class="wikitable"
! Agent !! Role !! Responsibility !! Implementation
|-
| '''The Lexicographer'''
| Data Generator
| Bootstrap dictionaries for new languages by generating morphological classes and seed lexicons (e.g., classifying "Apple" as a Noun with specific gender/plural forms).
| <code>ai_services/lexicographer.py</code>
|-
| '''The Surgeon'''
| Code Fixer
| Implements the "Self-Healing" build pipeline. Reads GF compiler error logs and surgically patches broken <code>.gf</code> source files to resolve API mismatches or syntax errors.
| <code>ai_services/surgeon.py</code>
|-
| '''The Judge'''
| Quality Assurance
| Generates "Gold Standard" reference sentences and validates the engine's output by scoring linguistic naturalness and accuracy against the source abstract intent.
| <code>ai_services/judge.py</code>
|}

== Directory Structure ==

All AI logic is centralized in the <code>ai_services/</code> directory to ensure consistent API handling and rate limiting.

<syntaxhighlight lang="text">
ai_services/
├── __init__.py           # Package exposure (exports surgeon, judge, lexicographer)
├── client.py             # Central Gemini client (API keys, Config, Rate Limiting)
├── lexicographer.py      # Logic for seeding dictionaries
├── surgeon.py            # Logic for repairing broken grammars
└── judge.py              # Logic for validation & gold standard generation
</syntaxhighlight>

== Configuration & Settings ==

The AI layer requires specific environment variables and file paths to function.

* '''Environment Variable:''' <code>GOOGLE_API_KEY</code> (Required in <code>.env</code> file).
* '''Model Selection:''' Defaults to <code>gemini-1.5-pro</code> for high-reasoning tasks (configured in <code>client.py</code>).
* '''Failure Report Path:''' <code>data/reports/build_failures.json</code> (The shared memory file used by the Compiler to pass error logs to the Surgeon).

== Core Modules ==

=== 1. The Client (client.py) ===
'''Entry Point:''' <code>ai_services/client.py</code>

This module manages the connection to the LLM provider, handling authentication, error states, and rate limiting centrally. It implements exponential backoff to handle API quotas robustly.

<syntaxhighlight lang="python">
import os
import time
import logging
import google.generativeai as genai
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = os.getenv("ARCHITECT_AI_MODEL", "gemini-1.5-pro")

# --- Logging Setup ---
logger = logging.getLogger("ai_services")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [AI] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_model = None

def _initialize():
    """Initializes the Gemini client (Singleton Pattern)."""
    global _model
    if _model: return True
    
    if not API_KEY:
        logger.error("Missing GOOGLE_API_KEY in environment variables.")
        return False

    try:
        genai.configure(api_key=API_KEY)
        _model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"Connected to Google AI ({MODEL_NAME})")
        return True
    except Exception as e:
        logger.critical(f"Connection failed: {e}")
        return False

def generate(prompt, max_retries=3):
    """
    Robust wrapper for text generation with error handling and backoff.
    """
    if not _initialize(): return ""

    wait_time = 2  # Start with 2 seconds wait

    for attempt in range(1, max_retries + 1):
        try:
            response = _model.generate_content(prompt)
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.warning(f"Blocked: {response.prompt_feedback.block_reason}")
                return ""
            return response.text.strip()

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(wait_time)
                wait_time *= 2
            else:
                logger.error("AI Generation failed after max retries.")
                return ""
    return ""
</syntaxhighlight>

=== 2. The Judge (judge.py) ===
'''Entry Point:''' <code>ai_services/judge.py</code>

The Judge is the Quality Assurance agent responsible for "grading" the output of the deterministic engine. It enforces strict JSON output schemas for machine readability.

<syntaxhighlight lang="python">
import json
import logging
from . import client

logger = logging.getLogger("ai_services.judge")

def _clean_json_response(response_text):
    """Helper to extract raw JSON from potential markdown wrapping."""
    if not response_text: return None
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        first_newline = clean_text.find("\n")
        if first_newline != -1: clean_text = clean_text[first_newline+1:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
    return clean_text.strip()

def generate_gold_standard(concepts, lang_name):
    """Generates reference sentences for a list of abstract concepts."""
    if not concepts or not lang_name: return []

    prompt = f"""
    Translate the following list of sentences into {lang_name}.
    Ensure the translation is natural but strictly grammatical.
    
    INPUT LIST: {json.dumps(concepts)}
    
    INSTRUCTIONS:
    Return ONLY a raw JSON list of strings. No markdown.
    Example output: ["Sentence 1", "Sentence 2"]
    """
    
    response = client.generate(prompt)
    clean_json = _clean_json_response(response)
    if not clean_json: return []

    try:
        data = json.loads(clean_json)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []

def evaluate_output(source_concept, generated_text, lang_name):
    """Scores the quality of the generated text against the source concept."""
    if not generated_text: return {"valid": False, "score": 0, "error": "Empty generation input"}

    prompt = f"""
    Act as a strict linguistic judge for the language: {lang_name}.
    TASK: Verify if the GENERATED TEXT correctly matches the SOURCE CONCEPT.
    SOURCE CONCEPT: "{source_concept}"
    GENERATED TEXT: "{generated_text}"
    
    OUTPUT FORMAT:
    Return strictly a JSON object with these keys:
    {{
        "valid": boolean,
        "score": integer (0-10),
        "correction": "string (the corrected sentence or null if perfect)"
    }}
    """
    
    response = client.generate(prompt)
    clean_json = _clean_json_response(response)
    if not clean_json: return {"valid": False, "score": 0, "error": "No valid response"}

    try:
        return json.loads(clean_json)
    except json.JSONDecodeError:
        return {"valid": False, "score": 0, "error": "JSON parse error"}
</syntaxhighlight>

=== 3. The Surgeon (surgeon.py) ===
'''Entry Point:''' <code>ai_services/surgeon.py</code>

The Surgeon is the repair agent for the "Self-Healing" pipeline. It uses compiler error logs to rewrite broken GF source code.

<syntaxhighlight lang="python">
import logging
from . import client

logger = logging.getLogger("ai_services.surgeon")

def _clean_gf_response(response_text):
    if not response_text: return None
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        first_newline = clean_text.find("\n")
        if first_newline != -1: clean_text = clean_text[first_newline+1:]
        if clean_text.endswith("```"): clean_text = clean_text[:-3]
    return clean_text.strip()

def repair_grammar(rgl_code, file_content, error_log):
    """Surgically repairs broken GF code based on compiler error logs."""
    logger.info(f"🤖 Surgeon: Analyzing compilation failure for {rgl_code}...")

    prompt = f"""
    You are an expert in Grammatical Framework (GF) and the Resource Grammar Library (RGL).
    CONTEXT: I am building a concrete syntax file (Wiki{rgl_code}.gf). The build failed.
    
    THE ERROR LOG:
    {error_log}
    
    THE BROKEN CODE:
    {file_content}
    
    YOUR MISSION:
    1. Analyze the error. 
       - If "constant not found", replace high-level API calls with lower-level constructors (e.g. MassNP, UseN).
       - If type mismatch, adjust parameters to match the expected record.
    2. Fix the code to make it compile.
    
    OUTPUT FORMAT: Return ONLY the full, corrected source code. No Markdown.
    """

    response_text = client.generate(prompt)
    fixed_code = _clean_gf_response(response_text)
    
    if fixed_code and "concrete" in fixed_code:
        return fixed_code
    else:
        logger.error(f"Surgeon failed: AI returned invalid code for {rgl_code}")
        return None
</syntaxhighlight>

=== 4. The Lexicographer (lexicographer.py) ===
'''Entry Point:''' <code>ai_services/lexicographer.py</code>

The Lexicographer automates the creation of new dictionaries, handling batch processing to respect token limits.

<syntaxhighlight lang="python">
import json
import logging
import math
from . import client

logger = logging.getLogger("ai_services.lexicographer")

def generate_lexicon(words, lang_name, batch_size=20):
    """Generates GF morphology dictionaries for a list of English words."""
    if not words or not lang_name: return {}

    full_lexicon = {}
    total_batches = math.ceil(len(words) / batch_size)
    
    for i in range(total_batches):
        batch = words[i * batch_size : (i + 1) * batch_size]
        
        prompt = f"""
        Act as an expert lexicographer for Grammatical Framework (GF).
        TASK: Generate morphology constructors for: {lang_name}.
        INPUT WORDS: {", ".join(batch)}
        
        INSTRUCTIONS:
        1. Identify part of speech (_N, _V, _A).
        2. Provide the correct GF constructor string (mkN, mkV, etc.).
        
        OUTPUT FORMAT: JSON object mapping ID to GF code.
        Example: {{ "apple_N": "mkN \\"pomme\\"" }}
        """
        
        response = client.generate(prompt)
        # (Parsing logic omitted for brevity; see implementation)
        # ... merges batch results into full_lexicon ...

    return full_lexicon
</syntaxhighlight>

== Pipeline Integration Points ==

The AI services are hooked into the build and test pipelines at specific failure or validation points.

=== A. Build Orchestrator (build_orchestrator.py) ===
'''Hook:''' <code>healer.run_healing_round()</code>

The orchestrator manages the high-level build loop. If the first compilation pass fails, it invokes the Healer. If the Healer reports success (patches applied), it triggers a second compilation pass.

<syntaxhighlight lang="python">
# 4. COMPILE & HEAL (The Muscle + The Surgeon)
print("\n--- [4/4] Compiling (Pass 1) ---")
success = compiler.run()

# --- SELF-HEALING LOOP ---
print("\n🚑 Analyzing Failures for AI Repair...")
patched = healer.run_healing_round()

if patched:
    print("\n🔄 Updates Applied. Compiling (Pass 2)...")
    success = compiler.run()
</syntaxhighlight>

=== B. The Healer (builder/healer.py) ===
'''Hook:''' <code>run_healing_round()</code>

The Healer acts as the bridge between the build system and the AI. It reads the <code>build_failures.json</code> report generated by the compiler, iterates through the failures, and dispatches the Surgeon to fix specific files. It also handles rate limiting to prevent API bans.

=== C. Dynamic Tester (test_gf_dynamic.py) ===
'''Hook:''' <code>judge.evaluate_output()</code>

During runtime testing, the Dynamic Tester calls the Judge to verify the semantic and grammatical accuracy of the generated text. This step is typically restricted to major languages or specific test runs to conserve API credits.

<syntaxhighlight lang="python">
if AI_AVAILABLE and lang_name in MAJOR_LANGS:
    verdict = judge.evaluate_output(source_concept, text, lang_name)
    if verdict.get('valid'):
        print(f"✅ Score: {verdict.get('score')}/10")
    else:
        print(f"⚠️ Fix: {verdict.get('correction')}")
</syntaxhighlight>

[[Category:Abstract Wikipedia tools]]