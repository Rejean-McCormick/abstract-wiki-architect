concrete WikiTam of AbstractWiki = open SyntaxTam, ParadigmsTam in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}