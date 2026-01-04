concrete WikiSpa of AbstractWiki = open SyntaxSpa, ParadigmsSpa in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}