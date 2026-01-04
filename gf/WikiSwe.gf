concrete WikiSwe of AbstractWiki = open SyntaxSwe, ParadigmsSwe in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}