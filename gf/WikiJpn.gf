concrete WikiJpn of AbstractWiki = open SyntaxJpn, ParadigmsJpn in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}