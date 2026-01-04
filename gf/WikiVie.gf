concrete WikiVie of AbstractWiki = open SyntaxVie, ParadigmsVie in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}