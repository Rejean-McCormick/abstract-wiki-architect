concrete WikiCgg of AbstractWiki = open SyntaxCgg, ParadigmsCgg in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}