concrete WikiPol of Wiki = GrammarPol, ParadigmsPol ** open SyntaxPol, (P = ParadigmsPol) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}