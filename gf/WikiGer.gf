concrete WikiGer of AbstractWiki = open SyntaxGer, ParadigmsGer in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}