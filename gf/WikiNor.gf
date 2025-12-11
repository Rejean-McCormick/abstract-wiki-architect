concrete WikiNor of Wiki = GrammarNor, ParadigmsNor ** open SyntaxNor, (P = ParadigmsNor) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}