concrete WikiMay of AbstractWiki = open SyntaxMay, ParadigmsMay in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}