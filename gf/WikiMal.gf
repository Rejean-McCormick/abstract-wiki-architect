concrete WikiMal of AbstractWiki = open SyntaxMal, ParadigmsMal in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}