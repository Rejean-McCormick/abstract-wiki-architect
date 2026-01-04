concrete WikiInd of AbstractWiki = open SyntaxInd, ParadigmsInd in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}