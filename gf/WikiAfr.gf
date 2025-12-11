concrete WikiAfr of Wiki = GrammarAfr, ParadigmsAfr ** open SyntaxAfr, (P = ParadigmsAfr) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}