import pgf

grammar = pgf.readPGF('gf/AbstractWiki.pgf')
eng = grammar.languages['WikiEng']
fra = grammar.languages['WikiFra']

# Construct an Abstract Tree: 'The animal walks'
# mkFact (lex_animal_N) (lex_walk_V)
expr = pgf.readExpr('mkFact lex_animal_N lex_walk_V')

print(f'[Abstract]: {expr}')
print(f'[English] : {eng.linearize(expr)}')
print(f'[French]  : {fra.linearize(expr)}')

