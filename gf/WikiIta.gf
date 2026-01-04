concrete WikiIta of AbstractWiki = open SyntaxIta, ParadigmsIta in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}