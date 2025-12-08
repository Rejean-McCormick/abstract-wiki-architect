import os
import pgf
import sys

def run_test():
    # 1. Locate PGF
    pgf_path = os.path.join("gf", "Wiki.pgf")
    if not os.path.exists(pgf_path):
        print(f"❌ PGF not found at {pgf_path}")
        print("   Did you run: docker-compose run --rm backend python gf/build_300.py ?")
        sys.exit(1)

    print(f"Loading grammar from: {pgf_path}...")
    try:
        grammar = pgf.readPGF(pgf_path)
    except Exception as e:
        print(f"❌ Failed to load PGF: {e}")
        sys.exit(1)

    languages = grammar.languages.keys()
    print(f"✅ Grammar loaded successfully.")
    print(f"🌍 Supported Languages ({len(languages)}):")
    print(f"   {', '.join(sorted(languages))}\n")

    # 2. Define a Universal Test Case
    # "The cat (entity) walks (predicate)"
    # This AST relies on the vocabulary we generated in build_300.py
    ast_expr = "mkFact cat_Entity walk_VP"
    
    print(f"🔬 Testing Linearization for AST: [{ast_expr}]")
    print("-" * 60)
    print(f"{'Language':<15} | {'Result':<40}")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    try:
        expr = pgf.readExpr(ast_expr)
    except Exception as e:
        print(f"❌ Syntax Error in test AST: {e}")
        sys.exit(1)

    # 3. Iterate over ALL languages in the grammar
    for lang_name in sorted(languages):
        concrete = grammar.languages[lang_name]
        try:
            # linearize returns a generator; look for the first variant
            text = concrete.linearize(expr)
            if text:
                print(f"{lang_name:<15} | {text}")
                success_count += 1
            else:
                print(f"{lang_name:<15} | (No linearization found)")
                fail_count += 1
        except Exception as e:
            print(f"{lang_name:<15} | ❌ ERROR: {e}")
            fail_count += 1

    print("-" * 60)
    print(f"Test Complete. Success: {success_count}, Failures: {fail_count}")

    if fail_count > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_test()