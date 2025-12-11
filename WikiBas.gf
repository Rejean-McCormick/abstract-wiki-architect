concrete WikiBas of Wiki = GrammarEus, ParadigmsEus ** open SyntaxEus, (P = ParadigmsEus) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}