concrete WikiSom of Wiki = CatSom, NounSom ** open SyntaxSom, (P = ParadigmsSom) in {

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