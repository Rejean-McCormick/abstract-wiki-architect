concrete WikiMon of AbstractWiki = WikiI ** open SyntaxMon, DictMon, SymbolicMon, Prelude in {
  lin
    animal_Entity = mkNP lex_animal_N ;
    mkLiteral v = symb v.s ;
} ;
