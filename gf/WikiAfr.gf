concrete WikiAfr of AbstractWiki = open SyntaxAfr, ParadigmsAfr in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}