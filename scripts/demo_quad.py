import pgf

grammar = pgf.readPGF('gf/AbstractWiki.pgf')
langs = grammar.languages

expr = pgf.readExpr('mkFact lex_animal_N lex_walk_V')

print(f'\n[Abstract]: {expr}')
print('-' * 30)
for lang_code in ['WikiEng', 'WikiFra', 'WikiGer', 'WikiSpa']:
    if lang_code in langs:
        print(f'[{lang_code[-3:]}]: {langs[lang_code].linearize(expr)}')

