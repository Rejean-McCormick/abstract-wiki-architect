concrete WikiIna of AbstractWiki = open SyntaxIna, ParadigmsIna in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}