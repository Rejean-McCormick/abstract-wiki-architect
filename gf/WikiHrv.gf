concrete WikiHrv of AbstractWiki = open SyntaxHrv, ParadigmsHrv in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}