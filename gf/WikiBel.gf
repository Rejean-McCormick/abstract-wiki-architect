concrete WikiBel of AbstractWiki = open SyntaxBel, ParadigmsBel in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}