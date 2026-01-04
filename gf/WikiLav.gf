concrete WikiLav of AbstractWiki = open SyntaxLav, ParadigmsLav in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}