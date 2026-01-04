concrete WikiGre of AbstractWiki = open SyntaxGre, ParadigmsGre in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}