concrete WikiEus of AbstractWiki = open SyntaxEus, ParadigmsEus in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}