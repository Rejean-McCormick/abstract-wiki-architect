incomplete concrete WikiI of AbstractWiki = open Syntax in {
  lincat
    Entity    = NP ;
    Property  = AP ;
    Predicate = VP ;
    Fact      = S ;
    Modifier  = Adv ;
    Value     = NP ;

  lin
    mkFact subj pred = mkS (mkCl subj pred) ;
    mkIsAProperty subj prop = mkS (mkCl subj prop) ;
    FactWithMod fact mod = mkS mod fact ;
    mkLiteral v = v ;
    Entity2NP e = e ;
    Property2AP p = p ;
    VP2Predicate p = p ;
}
