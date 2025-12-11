concrete WikiGer of Wiki = GrammarGer, ParadigmsGer ** open SyntaxGer, (P = ParadigmsGer) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}