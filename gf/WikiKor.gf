concrete WikiKor of AbstractWiki = open SyntaxKor, ParadigmsKor in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}