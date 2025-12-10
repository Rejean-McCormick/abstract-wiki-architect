concrete WikiLat of AbstractWiki = WikiI ** open SyntaxLat, SymbolicLat, DictLat, Prelude in {
  lin
    animal_Entity = mkNP lex_animal_N ;
    mkLiteral v = symb v.s ;
} ;
