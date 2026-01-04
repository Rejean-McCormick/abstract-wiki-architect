concrete WikiHun of AbstractWiki = open SyntaxHun, ParadigmsHun in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}