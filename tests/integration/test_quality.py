import pytest
import json
import os
from app.shared.config import settings
from ai_services.judge import judge
from app.core.engine import GrammarEngine

# Initialize the engine for testing
# Note: Ensure AbstractWiki.pgf is built before running these tests
engine = GrammarEngine(settings.PGF_PATH)

def load_gold_standard():
    """Loads the ground truth dataset for validation."""
    if not os.path.exists(settings.GOLD_STANDARD_PATH):
        pytest.skip(f"Gold standard file not found at {settings.GOLD_STANDARD_PATH}")
    
    with open(settings.GOLD_STANDARD_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# ==============================================================================
# QUALITY REGRESSION SUITE
# ==============================================================================

@pytest.mark.parametrize("case", load_gold_standard())
def test_language_quality_regression(case):
    """
    Integration test that validates generated text against the AI Judge.
    Logic:
    1. Generate text using the actual GF engine.
    2. Pass output to Judge Agent.
    3. Assert Judge Score > 0.8.
    """
    lang = case["lang"]
    intent = case["intent"]
    expected = case["expected"]
    
    # 1. Skip if language is not in the current binary
    if lang not in engine.languages:
        pytest.skip(f"Language {lang} not found in PGF binary.")

    # 2. Generate Output from Engine
    # We pass None for session context to test raw semantic accuracy
    result = engine.generate(intent, lang, context=None)
    generated_text = result.get("text", "")

    assert generated_text != "", f"Engine returned empty string for {lang}"

    # 3. Invoke The Judge
    # The Judge compares 'generated_text' with 'expected' and returns a score
    report = judge.evaluate_case(generated_text, case)

    # 4. Assertions
    # We allow a small margin for synonyms, but the Judge score must be high
    score = report.get("score", 0.0)
    verdict = report.get("verdict", "FAIL")
    critique = report.get("critique", "No critique provided.")

    print(f"\n[QA REPORT] Lang: {lang} | Score: {score} | Verdict: {verdict}")
    print(f"Detail: {critique}")

    assert score >= 0.8, (
        f"Quality Failure in {lang} ({case['id']}):\n"
        f"Expected: {expected}\n"
        f"Actual:   {generated_text}\n"
        f"Judge Critique: {critique}"
    )

def test_judge_connectivity():
    """Simple check to ensure the Judge Agent is online."""
    if not settings.GOOGLE_API_KEY:
        pytest.skip("AI testing skipped: GOOGLE_API_KEY missing.")
    
    assert judge._client is not None