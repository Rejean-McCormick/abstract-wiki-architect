concrete WikiLat of AbstractWiki = open SyntaxLat, ParadigmsLat in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}