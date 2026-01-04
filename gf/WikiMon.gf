concrete WikiMon of AbstractWiki = open SyntaxMon, ParadigmsMon in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}