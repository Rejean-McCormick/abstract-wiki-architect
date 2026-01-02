# tests/integration/test_quality.py
import pytest
import json
import os
from pathlib import Path
from app.shared.config import settings
from ai_services.judge import judge
from app.core.engine import GrammarEngine

# ==============================================================================
# SETUP & FIXTURES
# ==============================================================================

def load_gold_standard_cases():
    """
    Loads the ground truth dataset for validation during test collection.
    Returns an empty list if file is missing (to avoid collection crashes).
    """
    # Defensive check on settings presence
    if not hasattr(settings, "GOLD_STANDARD_PATH") or not settings.GOLD_STANDARD_PATH:
        return []

    path = Path(settings.GOLD_STANDARD_PATH)
    if not path.exists():
        return []
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

# Pre-load cases for parametrization
TEST_CASES = load_gold_standard_cases()

@pytest.fixture(scope="module")
def engine():
    """
    Initializes the GrammarEngine once for the whole test module.
    """
    # Ensure PGF path is set and valid
    pgf_path = getattr(settings, "PGF_PATH", "gf/AbstractWiki.pgf")
    
    if not os.path.exists(pgf_path):
        pytest.fail(f"PGF binary not found at {pgf_path}. Please build the grammar first.")
        
    return GrammarEngine(pgf_path)

# ==============================================================================
# QUALITY REGRESSION SUITE
# ==============================================================================

@pytest.mark.skipif(not TEST_CASES, reason=f"Gold standard file not found or empty at {getattr(settings, 'GOLD_STANDARD_PATH', 'UNKNOWN')}")
@pytest.mark.parametrize("case", TEST_CASES, ids=lambda c: f"{c.get('lang', 'unk')}-{c.get('id', 'unk')}")
def test_language_quality_regression(engine, case):
    """
    Integration test that validates generated text against the AI Judge.
    
    Steps:
    1. Generate text using the actual GF engine.
    2. Pass output to Judge Agent (LLM).
    3. Assert Judge Score > 0.8.
    """
    lang = case["lang"]
    intent = case["intent"]
    expected = case["expected"]
    case_id = case.get('id', 'unknown')
    
    # 1. Validation: Ensure language exists in binary
    if lang not in engine.languages:
        pytest.skip(f"Language {lang} not found in PGF binary.")

    # 2. Generation: Run the Engine
    # We pass context=None to test raw semantic capabilities
    generated_text = ""
    try:
        result = engine.generate(intent, lang, context=None)
        # Handle both dict return and object return depending on Engine version
        if isinstance(result, dict):
            generated_text = result.get("text", "").strip()
        else:
            generated_text = getattr(result, "text", "").strip()
            
    except Exception as e:
        # Capture full context of the crash
        pytest.fail(
            f"Engine generation crashed.\n"
            f"  Language: {lang}\n"
            f"  PGF:      {engine.pgf_path}\n"
            f"  Intent:   {intent}\n"
            f"  Error:    {str(e)}"
        )

    # Fail fast if output is empty
    assert generated_text, (
        f"Engine returned empty string.\n"
        f"  Language: {lang}\n"
        f"  Intent:   {intent}"
    )

    # 3. Evaluation: Invoke The AI Judge
    # The Judge compares 'generated_text' with 'expected'
    report = judge.evaluate_case(generated_text, case)

    score = report.get("score", 0.0)
    verdict = report.get("verdict", "FAIL")
    critique = report.get("critique", "No critique provided.")

    # 4. Reporting (Visible with pytest -s)
    # This helps during manual debugging runs
    print(f"\n[{verdict}] {lang} (ID: {case_id}) | Score: {score}")
    if score < 0.8:
        print(f"   Intent:   {intent}")
        print(f"   Expected: {expected}")
        print(f"   Actual:   {generated_text}")
        print(f"   Critique: {critique}")

    # 5. Assertion
    # Construct a detailed failure message for CI/GUI logs
    failure_msg = (
        f"\nQuality Failure in {lang} (ID: {case_id}):\n"
        f"---------------------------------------------------\n"
        f"Intent:   {intent}\n"
        f"Expected: {expected}\n"
        f"Actual:   {generated_text}\n"
        f"Score:    {score} (Threshold: 0.8)\n"
        f"Verdict:  {verdict}\n"
        f"Critique: {critique}\n"
        f"---------------------------------------------------"
    )
    
    assert score >= 0.8, failure_msg

def test_judge_connectivity():
    """Simple check to ensure the Judge Agent is online and configured."""
    if not getattr(settings, "GOOGLE_API_KEY", None):
        pytest.skip("AI testing skipped: GOOGLE_API_KEY missing.")
    
    # Ensure the client was actually initialized inside the judge singleton
    if not hasattr(judge, "_client") or judge._client is None:
        pytest.fail("Judge client is not initialized despite API Key presence.")