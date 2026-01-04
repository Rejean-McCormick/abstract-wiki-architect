concrete WikiFin of AbstractWiki = open SyntaxFin, ParadigmsFin in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}