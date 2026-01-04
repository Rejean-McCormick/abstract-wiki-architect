concrete WikiRon of AbstractWiki = open SyntaxRon, ParadigmsRon in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}