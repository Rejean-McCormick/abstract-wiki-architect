concrete WikiNno of AbstractWiki = open SyntaxNno, ParadigmsNno in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}