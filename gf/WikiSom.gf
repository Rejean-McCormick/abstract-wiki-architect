concrete WikiSom of Wiki = GrammarSom, ParadigmsSom ** open SyntaxSom, (P = ParadigmsSom) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}