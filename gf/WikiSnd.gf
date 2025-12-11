concrete WikiSnd of Wiki = GrammarSnd, ParadigmsSnd ** open SyntaxSnd, (P = ParadigmsSnd) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}