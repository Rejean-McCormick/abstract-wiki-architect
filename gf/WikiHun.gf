concrete WikiHun of Wiki = GrammarHun, ParadigmsHun ** open SyntaxHun, (P = ParadigmsHun) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}