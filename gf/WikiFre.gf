concrete WikiFre of AbstractWiki = WikiI ** open SyntaxFre, ParadigmsFre, SymbolicFre in {
  lin
    lex_animal_N = mkNP (mkN "animal");
    lex_walk_V = mkVP (mkV "walk");
    lex_blue_A = mkAP (mkA "blue"); 
    mkLiteral v = symb v.s;
};
