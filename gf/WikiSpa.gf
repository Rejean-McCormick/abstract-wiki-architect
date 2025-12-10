concrete WikiSpa of AbstractWiki = WikiI ** open SyntaxSpa, SymbolicSpa, DictSpa, Prelude in {
  lin
    lex_animal_N = mkNP (mkN "animal");
    lex_walk_V = mkVP (mkV "walk");
    lex_blue_A = mkAP (mkA "blue"); 
    mkLiteral v = symb v.s;
};
