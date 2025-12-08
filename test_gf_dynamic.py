import os
import pgf
import sys

def run_test():
    # 1. Locate PGF
    # In Docker, this maps to /app/gf/Wiki.pgf
    pgf_path = os.path.join("gf", "Wiki.pgf")
    
    if not os.path.exists(pgf_path):
        print(f"❌ PGF not found at {pgf_path}")
        print("   Did you run: docker-compose run --rm backend python gf/build_orchestrator.py ?")
        sys.exit(1)

    print(f"Loading grammar from: {pgf_path}...")
    try:
        grammar = pgf.readPGF(pgf_path)
    except Exception as e:
        print(f"❌ Failed to load PGF: {e}")
        sys.exit(1)

    languages = grammar.languages.keys()
    count = len(languages)
    print(f"✅ Grammar loaded successfully.")
    print(f"🌍 Supported Languages ({count}):")
    
    # Don't flood console if we have 300 languages
    sorted_langs = sorted(languages)
    if count > 20:
        print(f"   {', '.join(sorted_langs[:10])} ... {', '.join(sorted_langs[-10:])}")
    else:
        print(f"   {', '.join(sorted_langs)}")
    print("")

    # 2. Define a Universal Test Case
    # Corresponds to: "The cat walks"
    # Function names must match what is defined in build_orchestrator.py -> generate_abstract()
    ast_expr = "mkFact lex_cat_N lex_walk_V"
    
    print(f"🔬 Testing Linearization for AST: [{ast_expr}]")
    print("-" * 70)
    print(f"{'Language':<20} | {'Result':<45}")
    print("-" * 70)

    success_count = 0
    fail_count = 0

    try:
        expr = pgf.readExpr(ast_expr)
    except Exception as e:
        print(f"❌ Syntax Error in test AST: {e}")
        print("   (Your generated Abstract Grammar might have different function names)")
        sys.exit(1)

    # 3. Iterate over ALL languages in the grammar
    for lang_name in sorted_langs:
        concrete = grammar.languages[lang_name]
        try:
            # linearize returns a string directly in Python binding (or None)
            text = concrete.linearize(expr)
            
            if text:
                print(f"{lang_name:<20} | {text}")
                success_count += 1
            else:
                print(f"{lang_name:<20} | (No linearization found)")
                fail_count += 1
                
        except Exception as e:
            print(f"{lang_name:<20} | ❌ ERROR: {e}")
            fail_count += 1

    print("-" * 70)
    print(f"Test Complete. Success: {success_count}/{count}, Failures: {fail_count}/{count}")

    # Exit with error if significant failure (e.g. > 5%)
    # For now, strict:
    if fail_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_test()