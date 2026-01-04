concrete WikiDan of AbstractWiki = open SyntaxDan, ParadigmsDan in {
  lincat
    Fact = S ;
    Entity = NP ;
    Predicate = VP ;
  lin
    mkFact s p = mkS (mkCl s p) ;
}