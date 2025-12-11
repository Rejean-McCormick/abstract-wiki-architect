concrete WikiPor of Wiki = GrammarPor, ParadigmsPor ** open SyntaxPor, (P = ParadigmsPor) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}