concrete WikiUkr of AbstractWiki = open SyntaxUkr, ParadigmsUkr in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}