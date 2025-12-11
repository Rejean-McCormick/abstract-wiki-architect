concrete WikiFre of Wiki = GrammarFre, ParadigmsFre ** open SyntaxFre, (P = ParadigmsFre) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}