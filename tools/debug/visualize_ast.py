"""
Visualizes the Abstract Syntax Tree (AST) for a given sentence or abstract intent.

Usage:
    python tools/debug/visualize_ast.py --lang en --sentence "The cat eats the fish"
    python tools/debug/visualize_ast.py --ast "mkS (mkCl (mkNP (mkN \"cat_N\")) (mkV2 \"eat_V2\") (mkNP (mkN \"fish_N\")))"

Output:
    JSON structure representing the tree nodes, printed to stdout.
"""

import argparse
import json
import sys
import os
import re
import time
from typing import Dict, Any, List

# --- Setup Path to import from 'app' ---
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, "../../"))
sys.path.append(root_dir)

try:
    from app.shared.config import settings
except ImportError:
    try:
        from app.core.config import settings
    except ImportError:
        # Fallback for standalone usage
        class MockSettings:
            PGF_PATH = os.path.join(root_dir, "gf", "AbstractWiki.pgf")
        settings = MockSettings()

# [FIX] Import GFGrammarEngine explicitly
try:
    from app.adapters.engines.gf_wrapper import GFGrammarEngine
except ImportError:
    # We will log this error in the JSON response if engine is needed
    GFGrammarEngine = None

# Regex to tokenize the GF output
TOKENIZER_REGEX = re.compile(r'\(|\)|"[^"]*"|[^\s()]+')

def resolve_concrete_name(lang_code: str) -> str:
    """
    Resolves 'en' -> 'WikiEng' using the system configuration.
    """
    config_path = os.path.join(root_dir, "data", "config", "iso_to_wiki.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                iso_map = json.load(f)
            # Support v1 (str) and v2 (dict) schemas
            entry = iso_map.get(lang_code.lower())
            if entry:
                wiki_name = entry if isinstance(entry, str) else entry.get("wiki")
                if wiki_name: return wiki_name
        except Exception:
            pass
    return f"Wiki{lang_code.capitalize()}"

def parse_gf_string_to_json(ast_str: str) -> Dict[str, Any]:
    """
    Parses a bracketed GF string into a hierarchical JSON object.
    """
    tokens = TOKENIZER_REGEX.findall(ast_str)
    
    def _parse_recursive(token_iter):
        try:
            token = next(token_iter)
        except StopIteration:
            return None

        if token == '(':
            # Start of a new node
            try:
                func_name = next(token_iter)
            except StopIteration:
                return None
            
            children = []
            while True:
                child = _parse_recursive(token_iter)
                if child == ')':
                    break
                if child:
                    children.append(child)
            
            return {"name": func_name, "children": children, "type": "function"}
        
        elif token == ')':
            return ')'
        
        else:
            return {"name": token, "children": [], "type": "leaf"}

    iter_tokens = iter(tokens)
    if not ast_str.strip().startswith("("):
        return {"name": ast_str.strip(), "children": [], "type": "leaf"}

    return _parse_recursive(iter_tokens)

def main():
    parser = argparse.ArgumentParser(description="Generate JSON AST from GF output.")
    parser.add_argument("--lang", help="Language code (e.g. en, fr)")
    parser.add_argument("--sentence", help="Linear sentence to parse")
    parser.add_argument("--ast", help="Raw GF abstract syntax string")
    parser.add_argument("--pgf", default=None, help="Path to PGF file")

    args = parser.parse_args()
    pgf_path = args.pgf if args.pgf else settings.PGF_PATH

    # --- Initialize JSON-Safe Logging ---
    # We do NOT use the standard logger here because we must output valid JSON to stdout.
    output_logs = []
    def log(msg): 
        timestamp = time.strftime("%H:%M:%S")
        output_logs.append(f"[{timestamp}] {msg}")

    # Prepare Response Structure
    response = {
        "meta": {
            "tool": "visualize_ast",
            "version": "2.1",
            "timestamp": time.time(),
            "input_mode": "ast" if args.ast else "sentence",
            "pgf_path": str(pgf_path),
            "durations_ms": {}
        },
        "logs": output_logs,
        "warnings": [],
        "tree": None,
        "status": "pending"
    }

    try:
        log("Tool started.")
        
        # 1. Initialize Engine (if needed)
        engine = None
        if args.sentence:
            if not GFGrammarEngine:
                raise ImportError("GFGrammarEngine not found. Check app.adapters.engines.")
            
            log(f"Initializing GFGrammarEngine with: {pgf_path}")
            t0 = time.time()
            engine = GFGrammarEngine(lib_path=pgf_path)
            response["meta"]["durations_ms"]["load_pgf"] = int((time.time() - t0) * 1000)

        final_ast_str = ""

        # 2. Strategy A: Parse a natural language sentence
        if args.sentence and args.lang:
            concrete_lang = resolve_concrete_name(args.lang)
            response["meta"]["concrete_lang"] = concrete_lang
            log(f"Parsing sentence: '{args.sentence}'")
            log(f"Target grammar: {concrete_lang}")
            
            t0 = time.time()
            try:
                # GFGrammarEngine.parse returns an iterator
                parses = list(engine.parse(args.sentence, language=concrete_lang))
                response["meta"]["durations_ms"]["parse"] = int((time.time() - t0) * 1000)
                
                if not parses:
                    msg = f"No parse trees found for input in {concrete_lang}"
                    response["warnings"].append(msg)
                    log(f"WARNING: {msg}")
                    final_ast_str = "NO_PARSE_FOUND"
                else:
                    final_ast_str = str(parses[0])
                    log(f"Success: Found {len(parses)} trees. Visualizing top result.")
            except Exception as e:
                response["warnings"].append(f"Engine parse error: {str(e)}")
                raise

        # 3. Strategy B: Visualize an existing AST string directly
        elif args.ast:
            final_ast_str = args.ast
            log("Mode: Direct AST visualization.")

        else:
             raise ValueError("Must provide either --ast OR (--sentence AND --lang).")

        # 4. Convert to JSON
        t0 = time.time()
        tree_json = parse_gf_string_to_json(final_ast_str)
        response["meta"]["durations_ms"]["build_json"] = int((time.time() - t0) * 1000)
        
        response["status"] = "success"
        response["raw_ast"] = final_ast_str
        response["tree"] = tree_json
        
        log("Visualization complete.")

    except Exception as e:
        response["status"] = "error"
        response["error"] = {
            "type": type(e).__name__,
            "message": str(e),
            "hint": "Check PGF path, grammar definitions, or input syntax."
        }
        log(f"CRITICAL ERROR: {str(e)}")
        # We catch all exceptions to ensure we still print valid JSON
        
    # Final Output: Pure JSON to STDOUT
    print(json.dumps(response, indent=2))

if __name__ == "__main__":
    main()