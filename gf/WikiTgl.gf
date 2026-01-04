concrete WikiTgl of AbstractWiki = open SyntaxTgl, ParadigmsTgl in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}