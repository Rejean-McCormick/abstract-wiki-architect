concrete WikiGre of Wiki = GrammarGre, ParadigmsGre ** open SyntaxGre, (P = ParadigmsGre) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}