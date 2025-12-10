concrete WikiNep of AbstractWiki = WikiI ** open SyntaxNep, DictNep, SymbolicNep, Prelude in {
  lin
    animal_Entity = mkNP lex_animal_N ;
    mkLiteral v = symb v.s ;
} ;
