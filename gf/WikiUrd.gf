concrete WikiUrd of AbstractWiki = open SyntaxUrd, ParadigmsUrd in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}