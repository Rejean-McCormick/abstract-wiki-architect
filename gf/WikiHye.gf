concrete WikiHye of AbstractWiki = open SyntaxHye, ParadigmsHye in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}