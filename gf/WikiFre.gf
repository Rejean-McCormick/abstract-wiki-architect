concrete WikiFre of AbstractWiki = open SyntaxFre, ParadigmsFre in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}