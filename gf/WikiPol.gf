concrete WikiPol of AbstractWiki = WikiI ** open SyntaxPol, SymbolicPol, DictPol, Prelude in {
  lin
    animal_Entity = mkNP lex_animal_N ;
    mkLiteral v = symb v.s ;
} ;
