concrete WikiSco of AbstractWiki = open SyntaxSco, ParadigmsSco in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}