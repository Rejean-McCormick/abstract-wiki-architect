concrete WikiPes of AbstractWiki = open SyntaxPes, ParadigmsPes in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}