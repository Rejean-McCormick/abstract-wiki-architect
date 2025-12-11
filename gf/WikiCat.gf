concrete WikiCat of Wiki = GrammarCat, ParadigmsCat ** open SyntaxCat, (P = ParadigmsCat) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}