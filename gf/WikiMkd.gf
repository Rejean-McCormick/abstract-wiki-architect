concrete WikiMkd of AbstractWiki = open SyntaxMkd, ParadigmsMkd in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}