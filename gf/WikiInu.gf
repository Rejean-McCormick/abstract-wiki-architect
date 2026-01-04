concrete WikiInu of AbstractWiki = open SyntaxInu, ParadigmsInu in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}