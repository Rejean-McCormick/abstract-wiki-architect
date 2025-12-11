concrete WikiEst of Wiki = GrammarEst, ParadigmsEst ** open SyntaxEst, (P = ParadigmsEst) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}