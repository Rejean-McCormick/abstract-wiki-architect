concrete WikiFin of Wiki = GrammarFin, ParadigmsFin ** open SyntaxFin, (P = ParadigmsFin) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}