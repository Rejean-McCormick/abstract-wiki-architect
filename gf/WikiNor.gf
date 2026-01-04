concrete WikiNor of AbstractWiki = open SyntaxNor, ParadigmsNor in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}