concrete WikiUrd of Wiki = GrammarUrd, ParadigmsUrd ** open SyntaxUrd, (P = ParadigmsUrd) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}