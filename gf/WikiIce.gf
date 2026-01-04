concrete WikiIce of AbstractWiki = open SyntaxIce, ParadigmsIce in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}