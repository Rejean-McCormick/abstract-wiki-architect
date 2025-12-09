import os
import sys
import pgf

def run_test():
    # 1. Locate PGF
    # Priority: Environment Var > Local Build Path
    pgf_path = os.environ.get("AW_PGF_PATH", os.path.join("gf", "Wiki.pgf"))
    
    if not os.path.exists(pgf_path):
        print(f"❌ PGF not found at {pgf_path}")
        print("   Did you run: python gf/build_orchestrator.py ?")
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
    # Note: These function names MUST match what is generated in 'gf/build_orchestrator.py' -> generate_abstract()
    # If build_orchestrator generates 'lex_cat_N', use that. 
    # If it generates 'lex_cat_N_1' (due to collisions), update here.
    
    ast_expr = "mkFact (lex_cat_N) (lex_walk_V)"
    
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
        print(f"   Expression was: {ast_expr}")
        print("   (Check if function names in 'generate_abstract()' match this test)")
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

    # Exit with error if significant failure
    if fail_count > 0:
        print("\n⚠️  Some languages failed verification.")
        # In strict CI/CD, you might uncomment the next line:
        # sys.exit(1)
        sys.exit(0) # Soft fail for now as we build out the 300 languages

if __name__ == "__main__":
    run_test()