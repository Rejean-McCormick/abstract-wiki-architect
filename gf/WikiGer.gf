concrete WikiGer of AbstractWiki = WikiI with (Syntax = SyntaxGer) ** open SyntaxGer, ParadigmsGer in { 
  lin
    -- We explicitly tell GF that Tier is 'neuter'
    lex_animal_N = mkNP the_Det (mkN "Tier" neuter) ;
    lex_walk_V   = mkVP (mkV "gehen") ;
    lex_blue_A   = mkAP (mkA "blau") ;
} ;
