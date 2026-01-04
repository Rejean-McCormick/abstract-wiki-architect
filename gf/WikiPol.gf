concrete WikiPol of AbstractWiki = open SyntaxPol, ParadigmsPol in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}