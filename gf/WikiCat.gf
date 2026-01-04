concrete WikiCat of AbstractWiki = open SyntaxCat, ParadigmsCat in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}