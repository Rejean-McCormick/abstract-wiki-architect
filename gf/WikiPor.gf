concrete WikiPor of AbstractWiki = open SyntaxPor, ParadigmsPor in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}