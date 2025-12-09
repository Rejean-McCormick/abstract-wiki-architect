concrete WikiEng of AbstractWiki = WikiI ** open SyntaxEng, ParadigmsEng, SymbolicEng in {
  lin
    lex_animal_N = mkNP (mkN "animal");
    lex_walk_V = mkVP (mkV "walk");
    lex_blue_A = mkAP (mkA "blue"); 
    mkLiteral v = symb v.s;
};
