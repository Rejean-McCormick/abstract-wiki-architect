concrete WikiSpa of Wiki = GrammarSpa, ParadigmsSpa ** open SyntaxSpa, (P = ParadigmsSpa) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}