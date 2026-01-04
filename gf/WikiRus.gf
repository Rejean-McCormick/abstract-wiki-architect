concrete WikiRus of AbstractWiki = open SyntaxRus, ParadigmsRus in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}