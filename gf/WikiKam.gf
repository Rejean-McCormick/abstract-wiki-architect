concrete WikiKam of AbstractWiki = open SyntaxKam, ParadigmsKam in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}