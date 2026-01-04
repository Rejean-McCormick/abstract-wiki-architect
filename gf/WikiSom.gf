concrete WikiSom of AbstractWiki = open SyntaxSom, ParadigmsSom in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}