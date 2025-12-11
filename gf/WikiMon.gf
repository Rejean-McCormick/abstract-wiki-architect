concrete WikiMon of Wiki = GrammarMon, ParadigmsMon ** open SyntaxMon, (P = ParadigmsMon) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}