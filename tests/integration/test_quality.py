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
    if not os.path.exists(settings.PGF_PATH):
        pytest.fail(f"PGF binary not found at {settings.PGF_PATH}. Please build the grammar first.")
    return GrammarEngine(settings.PGF_PATH)

# ==============================================================================
# QUALITY REGRESSION SUITE
# ==============================================================================

@pytest.mark.skipif(not TEST_CASES, reason=f"Gold standard file not found or empty at {settings.GOLD_STANDARD_PATH}")
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
    
    # 1. Validation: Ensure language exists in binary
    if lang not in engine.languages:
        pytest.skip(f"Language {lang} not found in PGF binary.")

    # 2. Generation: Run the Engine
    # We pass context=None to test raw semantic capabilities
    try:
        result = engine.generate(intent, lang, context=None)
        generated_text = result.get("text", "").strip()
    except Exception as e:
        pytest.fail(f"Engine generation crashed for {lang}: {str(e)}")

    assert generated_text, f"Engine returned empty string for {lang}"

    # 3. Evaluation: Invoke The AI Judge
    # The Judge compares 'generated_text' with 'expected'
    report = judge.evaluate_case(generated_text, case)

    score = report.get("score", 0.0)
    verdict = report.get("verdict", "FAIL")
    critique = report.get("critique", "No critique provided.")

    # 4. Reporting (Visible with pytest -s)
    print(f"\n[{verdict}] {lang} (ID: {case.get('id')}) | Score: {score}")
    if score < 0.8:
        print(f"   Intent:   {intent}")
        print(f"   Expected: {expected}")
        print(f"   Actual:   {generated_text}")
        print(f"   Critique: {critique}")

    # 5. Assertion
    assert score >= 0.8, (
        f"\nQuality Failure in {lang} (ID: {case['id']}):\n"
        f"---------------------------------------------------\n"
        f"Intent:   {intent}\n"
        f"Expected: {expected}\n"
        f"Actual:   {generated_text}\n"
        f"Score:    {score}\n"
        f"Critique: {critique}\n"
        f"---------------------------------------------------"
    )

def test_judge_connectivity():
    """Simple check to ensure the Judge Agent is online and configured."""
    if not settings.GOOGLE_API_KEY:
        pytest.skip("AI testing skipped: GOOGLE_API_KEY missing.")
    
    assert judge._client is not None, "Judge client is not initialized."