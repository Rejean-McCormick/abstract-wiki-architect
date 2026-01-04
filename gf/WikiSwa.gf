concrete WikiSwa of AbstractWiki = open SyntaxSwa, ParadigmsSwa in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}