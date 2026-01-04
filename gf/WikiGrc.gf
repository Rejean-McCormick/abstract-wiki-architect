concrete WikiGrc of AbstractWiki = open SyntaxGrc, ParadigmsGrc in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}