concrete WikiSlo of AbstractWiki = open SyntaxSlo, ParadigmsSlo in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}