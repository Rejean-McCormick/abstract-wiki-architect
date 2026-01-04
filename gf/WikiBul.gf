concrete WikiBul of AbstractWiki = open SyntaxBul, ParadigmsBul in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}