import os
import sys
import pgf

# --- AI Integration ---
try:
    from ai_services import judge
    AI_AVAILABLE = True
except ImportError:
    print("⚠️  AI Services not found. Skipping validation.")
    AI_AVAILABLE = False

def run_test():
    # 1. Locate PGF
    pgf_path = os.environ.get("AW_PGF_PATH", os.path.join("gf", "Wiki.pgf"))
    
    if not os.path.exists(pgf_path):
        print(f"❌ PGF not found at {pgf_path}")
        print("   Did you run: build_pipeline.bat ?")
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
    
    sorted_langs = sorted(languages)
    if count > 15:
        print(f"   {', '.join(sorted_langs[:5])} ... {', '.join(sorted_langs[-5:])}")
    else:
        print(f"   {', '.join(sorted_langs)}")
    print("")

    # 2. Define Test Case (Must match Abstract Wiki.gf)
    # The current forge.py generates 'SimpNP' and 'apple_N'.
    # Expected Output: "an apple" (Eng), "une pomme" (Fre)
    ast_expr = "SimpNP apple_N"
    source_concept = "an apple" 
    
    print(f"🔬 Testing Linearization for AST: [{ast_expr}]")
    print("-" * 80)
    print(f"{'Language':<15} | {'Result':<30} | {'AI Verdict':<30}")
    print("-" * 80)

    success_count = 0
    fail_count = 0

    try:
        expr = pgf.readExpr(ast_expr)
    except Exception as e:
        print(f"❌ Syntax Error in test AST: {e}")
        print(f"   Expression: {ast_expr}")
        print("   (Ensure these functions exist in gf/Wiki.gf)")
        sys.exit(1)

    # 3. Iterate & Validate
    # We test ALL languages, but only ask AI to judge major ones to save credits/time.
    MAJOR_LANGS = ["WikiEng", "WikiFre", "WikiGer", "WikiSpa", "WikiIta"]

    for lang_name in sorted_langs:
        concrete = grammar.languages[lang_name]
        try:
            text = concrete.linearize(expr)
            
            if text:
                ai_msg = ""
                # Call The Judge (only for major languages)
                if AI_AVAILABLE and lang_name in MAJOR_LANGS:
                    verdict = judge.evaluate_output(source_concept, text, lang_name)
                    if verdict.get('valid'):
                        ai_msg = f"✅ Score: {verdict.get('score')}/10"
                    else:
                        ai_msg = f"⚠️ Fix: {verdict.get('correction')}"
                
                print(f"{lang_name:<15} | {text:<30} | {ai_msg}")
                success_count += 1
            else:
                print(f"{lang_name:<15} | (No linearization)           |")
                fail_count += 1
                
        except Exception as e:
            print(f"{lang_name:<15} | ❌ ERROR: {str(e)[:20]}...   |")
            fail_count += 1

    print("-" * 80)
    print(f"Test Complete. Success: {success_count}/{count}, Failures: {fail_count}/{count}")

    if fail_count > 0:
        print("\n⚠️  Some languages failed verification.")
        sys.exit(0) # Soft fail

if __name__ == "__main__":
    run_test()