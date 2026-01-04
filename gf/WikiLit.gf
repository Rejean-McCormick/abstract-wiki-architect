concrete WikiLit of AbstractWiki = open SyntaxLit, ParadigmsLit in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}