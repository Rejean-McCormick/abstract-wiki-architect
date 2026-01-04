concrete WikiEng of AbstractWiki = open SyntaxEng, ParadigmsEng in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}