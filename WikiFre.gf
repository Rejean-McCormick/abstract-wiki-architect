concrete WikiFre of Wiki = CatFre, NounFre ** open SyntaxFre, (P = ParadigmsFre) in {

  lin
    -- Structural
    SimpNP cn = mkNP cn ;

    -- Lexicon
    -- We use standard Syntax constructors (mkNP, mkCN) directly
    -- We use Paradigms constructors (P.mkPN, P.mkN, P.mkAdv) via P
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}