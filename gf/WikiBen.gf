concrete WikiBen of AbstractWiki = open SyntaxBen, ParadigmsBen in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}