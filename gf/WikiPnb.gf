concrete WikiPnb of AbstractWiki = open SyntaxPnb, ParadigmsPnb in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}