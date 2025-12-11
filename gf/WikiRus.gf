concrete WikiRus of Wiki = GrammarRus, ParadigmsRus ** open SyntaxRus, (P = ParadigmsRus) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}