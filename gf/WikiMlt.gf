concrete WikiMlt of Wiki = GrammarMlt, ParadigmsMlt ** open SyntaxMlt, (P = ParadigmsMlt) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}