concrete WikiAra of Wiki = GrammarAra, ParadigmsAra ** open SyntaxAra, (P = ParadigmsAra) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}