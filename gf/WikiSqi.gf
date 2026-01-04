concrete WikiSqi of AbstractWiki = open SyntaxSqi, ParadigmsSqi in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}