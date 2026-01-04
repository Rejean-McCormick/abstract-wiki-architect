concrete WikiGla of AbstractWiki = open SyntaxGla, ParadigmsGla in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}