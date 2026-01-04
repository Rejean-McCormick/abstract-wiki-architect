concrete WikiHin of AbstractWiki = open SyntaxHin, ParadigmsHin in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}