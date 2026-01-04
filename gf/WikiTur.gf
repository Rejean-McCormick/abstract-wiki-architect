concrete WikiTur of AbstractWiki = open SyntaxTur, ParadigmsTur in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}