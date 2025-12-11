concrete WikiPan of Wiki = GrammarPnb, ParadigmsPnb ** open SyntaxPnb, (P = ParadigmsPnb) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}