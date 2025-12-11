concrete WikiLav of Wiki = GrammarLav, ParadigmsLav ** open SyntaxLav, (P = ParadigmsLav) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}