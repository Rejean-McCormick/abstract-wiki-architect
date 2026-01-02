# tests/test_gf_dynamic.py
import os
import sys
import pytest
import pgf

# --- Configuration ---
# Allow override via env var, default to the standard build path
PGF_PATH = os.environ.get("AW_PGF_PATH", os.path.join("gf", "AbstractWiki.pgf"))

# --- AI Integration Setup ---
try:
    from ai_services import judge
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

# --- Fixtures ---

@pytest.fixture(scope="module")
def grammar():
    """
    Loads the PGF grammar once for the module.
    Skips the test suite if the binary is missing.
    """
    if not os.path.exists(PGF_PATH):
        pytest.skip(
            f"PGF binary not found at {PGF_PATH}. "
            "Run 'builder/orchestrator.py' or 'make build' to generate it."
        )
    
    try:
        return pgf.readPGF(PGF_PATH)
    except Exception as e:
        pytest.fail(f"Failed to load PGF at {PGF_PATH}: {e}")

# --- Tests ---

def test_grammar_has_supported_languages(grammar):
    """
    Ensures the grammar isn't empty and lists supported languages.
    """
    languages = grammar.languages.keys()
    count = len(languages)
    
    assert count > 0, f"PGF at {PGF_PATH} contains 0 languages."
    
    # Log for GUI/CLI visibility
    sorted_langs = sorted(languages)
    print(f"\n🌍 Supported Languages ({count}): {', '.join(sorted_langs)}")

def test_linearize_simple_phrase(grammar):
    """
    Smoke test: Linearize a basic AST in all available languages.
    AST: 'SimpNP apple_N' (an apple / une pomme)
    """
    # 1. Define Test AST
    ast_expr = "SimpNP apple_N"
    source_concept = "an apple"
    
    try:
        expr = pgf.readExpr(ast_expr)
    except Exception as e:
        pytest.fail(f"Syntax Error in test AST '{ast_expr}': {e}")

    # 2. Iterate & Validate
    failures = []
    success_count = 0
    
    # We test ALL languages found in the PGF
    for lang_name in sorted(grammar.languages.keys()):
        concrete = grammar.languages[lang_name]
        
        try:
            text = concrete.linearize(expr)
            
            if not text:
                failures.append(f"{lang_name}: Returned empty string")
                continue

            # Optional: AI Judging for major languages
            # We don't fail the test on AI verdict, just report it
            ai_msg = ""
            if AI_AVAILABLE and lang_name in ["WikiEng", "WikiFre", "WikiGer"]:
                try:
                    verdict = judge.evaluate_output(source_concept, text, lang_name)
                    if not verdict.get('valid', True):
                        ai_msg = f" [AI Warn: {verdict.get('correction')}]"
                except Exception:
                    pass # Don't let AI flakiness break the build

            print(f"   [OK] {lang_name:<15} -> {text}{ai_msg}")
            success_count += 1

        except Exception as e:
            failures.append(f"{lang_name}: Linearization error - {e}")

    # 3. Assert Results
    if failures:
        failure_report = "\n".join(failures)
        pytest.fail(
            f"Linearization failed for {len(failures)} languages.\n"
            f"AST: {ast_expr}\n"
            f"Failures:\n{failure_report}"
        )
    
    assert success_count > 0, "No languages were linearized."