concrete WikiKaz of AbstractWiki = open SyntaxKaz, ParadigmsKaz in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}