concrete WikiFao of AbstractWiki = open SyntaxFao, ParadigmsFao in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}