concrete WikiHeb of AbstractWiki = open SyntaxHeb, ParadigmsHeb in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}