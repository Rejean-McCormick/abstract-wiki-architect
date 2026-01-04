concrete WikiMlt of AbstractWiki = open SyntaxMlt, ParadigmsMlt in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}