concrete WikiEng of Wiki = GrammarEng, ParadigmsEng ** open SyntaxEng, (P = ParadigmsEng) in {
  lin
    SimpNP cn = mkNP cn ;
    John = mkNP (P.mkPN "John") ; 
    Here = P.mkAdv "here" ;
    apple_N = mkCN (P.mkN "apple") ;
}