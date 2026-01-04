concrete WikiZul of AbstractWiki = open SyntaxZul, ParadigmsZul in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}