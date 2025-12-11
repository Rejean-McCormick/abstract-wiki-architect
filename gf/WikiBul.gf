concrete WikiBul of Wiki = GrammarBul, ParadigmsBul ** open SyntaxBul, (P = ParadigmsBul) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}