concrete WikiTha of Wiki = GrammarTha, ParadigmsTha ** open SyntaxTha, (P = ParadigmsTha) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}