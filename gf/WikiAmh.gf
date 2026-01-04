concrete WikiAmh of AbstractWiki = open SyntaxAmh, ParadigmsAmh in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}