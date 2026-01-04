concrete WikiNep of AbstractWiki = open SyntaxNep, ParadigmsNep in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}