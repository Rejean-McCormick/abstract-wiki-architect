concrete WikiNep of Wiki = GrammarNep, ParadigmsNep ** open SyntaxNep, (P = ParadigmsNep) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}