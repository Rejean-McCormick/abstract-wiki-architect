import pgf

try:
    print('🔄 Loading PGF...')
    grammar = pgf.readPGF('gf/AbstractWiki.pgf')
    print('✅ PGF Loaded Successfully!')
    
    langs = grammar.languages.keys()
    print(f'🌍 Detected Languages: {list(langs)}')
    
    if 'WikiEng' in langs and 'WikiFra' in langs:
        print('🚀 SYSTEM READY: English and French are linked.')
    else:
        print('⚠️ CRITICAL: Languages missing.')

except Exception as e:
    print(f'❌ Error: {e}')

