concrete WikiLat of Wiki = GrammarLat, ParadigmsLat ** open SyntaxLat, (P = ParadigmsLat) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}