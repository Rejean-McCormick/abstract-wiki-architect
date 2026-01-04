concrete WikiCze of AbstractWiki = open SyntaxCze, ParadigmsCze in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}