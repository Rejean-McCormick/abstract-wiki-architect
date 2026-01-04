concrete WikiTel of AbstractWiki = open SyntaxTel, ParadigmsTel in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}