import os
import pgf

# 1. Load the PGF
pgf_path = os.path.join("gf", "Wiki.pgf")
if not os.path.exists(pgf_path):
    print(f"❌ PGF not found at {pgf_path}")
    exit(1)

grammar = pgf.readPGF(pgf_path)
print(f"✅ Loaded Grammar. Languages: {grammar.languages.keys()}")

# 2. Define a test Abstract Syntax Tree (AST)
# "The cat (entity) walks (predicate)"
# Abstract: mkFact cat_Entity walk_VP
ast_expr = "mkFact cat_Entity walk_VP"
expr = pgf.readExpr(ast_expr)

# 3. Linearize in a few languages
langs_to_test = ["WikiEng", "WikiFra", "WikiDeu", "WikiSpa"]

print(f"\nTesting AST: {ast_expr}")
for lang_name in langs_to_test:
    if lang_name in grammar.languages:
        lang = grammar.languages[lang_name]
        try:
            # linearize returns a generator, we take the first result
            text = lang.linearize(expr)
            print(f"  {lang_name}: {text}")
        except Exception as e:
            print(f"  {lang_name}: Error ({e})")
    else:
        print(f"  {lang_name}: Not found in PGF")