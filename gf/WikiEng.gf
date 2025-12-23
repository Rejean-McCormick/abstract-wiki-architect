concrete WikiEng of AbstractWiki = WikiI with (Syntax = SyntaxEng) ** open SyntaxEng, ParadigmsEng in { 
  lin
    -- mkNP : Det -> N -> NP
    lex_animal_N = mkNP the_Det (mkN "animal") ;
    lex_walk_V   = mkVP (mkV "walk") ;
    lex_blue_A   = mkAP (mkA "blue") ;
} ;
