concrete WikiAra of AbstractWiki = open SyntaxAra, ParadigmsAra in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}