concrete WikiKor of Wiki = GrammarKor, ParadigmsKor ** open SyntaxKor, (P = ParadigmsKor) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}