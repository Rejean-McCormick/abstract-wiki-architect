concrete WikiTha of AbstractWiki = open SyntaxTha, ParadigmsTha in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}