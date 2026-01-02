# tests/test_multilingual_generation.py
import pytest
import os
import sys
import pgf

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.engines.gf_wrapper import GFGrammarEngine

# --- FIXTURES ---

@pytest.fixture(scope="module")
def gf_engine():
    """
    Initializes the GF Engine once for the test module.
    """
    engine = GFGrammarEngine()
    
    # Robust check for grammar existence
    if not engine.grammar:
        pytest.skip(
            "Wiki.pgf not found. "
            "Run 'python builder/orchestrator.py' to build the grammar."
        )
    return engine

# --- HELPER ---

def linearize(engine, ast_expr, lang_code):
    """Helper to linearize a PGF Expression."""
    conc_name = engine._resolve_concrete_name(lang_code)
    if not conc_name:
        return None
    
    if isinstance(ast_expr, str):
        try:
            ast_expr = pgf.readExpr(ast_expr)
        except Exception:
            return None

    concrete = engine.grammar.languages[conc_name]
    return concrete.linearize(ast_expr)

# --- TESTS ---

def test_engine_languages(gf_engine):
    """Verify that the engine loaded English as a baseline."""
    langs = list(gf_engine.grammar.languages.keys())
    assert "WikiEng" in langs, (
        f"English concrete syntax (WikiEng) missing from PGF.\n"
        f"Loaded: {langs}"
    )

def test_literal_generation(gf_engine):
    """Test converting simple string literals (Ninai -> AST -> Text)."""
    ninai_input = "Hello World"
    lang = "eng"
    
    # 1. Convert to AST
    ast_str = gf_engine._convert_to_gf_ast(ninai_input, lang)
    
    # 2. Assert AST Structure
    assert '"Hello World"' in ast_str, (
        f"AST generation failed for literal.\n"
        f"Input: {ninai_input}\n"
        f"AST:   {ast_str}"
    )
    
    # 3. Linearize
    text = linearize(gf_engine, ast_str, lang)
    assert text == "Hello World", (
        f"Linearization mismatch.\n"
        f"Lang:   {lang}\n"
        f"AST:    {ast_str}\n"
        f"Output: {text}"
    )

def test_transitive_event(gf_engine):
    """Test: 'The cat eats the fish' (Transitive Predication)."""
    ninai_obj = {
        "function": "mkCl",
        "args": [
            {
                "function": "mkNP",
                "args": [{"function": "mkN", "args": ["cat"]}]
            },
            {
                "function": "mkV2",
                "args": ["eat"]
            },
            {
                "function": "mkNP",
                "args": [{"function": "mkN", "args": ["fish"]}]
            }
        ]
    }
    lang = "eng"

    # 1. Convert
    ast_str = gf_engine._convert_to_gf_ast(ninai_obj, lang)
    
    # 2. Check AST key components
    for token in ["mkCl", "mkNP", "mkV2", "cat", "fish"]:
        assert token in ast_str, f"Missing '{token}' in generated AST: {ast_str}"
    
    # 3. Linearize
    text_en = linearize(gf_engine, ast_str, lang)
    
    # Allow for some variation (determiners), but key lemmas must exist
    assert text_en and "cat" in text_en.lower() and "fish" in text_en.lower(), (
        f"Output text missing keywords.\n"
        f"Lang:   {lang}\n"
        f"AST:    {ast_str}\n"
        f"Output: {text_en}"
    )

def test_error_handling_invalid_ninai(gf_engine):
    """Test that invalid Ninai Objects raise strict errors with context."""
    invalid_obj = {
        "missing_function_key": "true",
        "args": []
    }
    
    with pytest.raises(ValueError) as excinfo:
        gf_engine._convert_to_gf_ast(invalid_obj, "eng")
    
    assert "Missing function attribute" in str(excinfo.value)