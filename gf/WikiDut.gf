concrete WikiDut of AbstractWiki = open SyntaxDut, ParadigmsDut in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}