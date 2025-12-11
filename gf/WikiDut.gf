concrete WikiDut of Wiki = GrammarDut, ParadigmsDut ** open SyntaxDut, (P = ParadigmsDut) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}