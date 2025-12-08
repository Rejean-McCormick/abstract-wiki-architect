incomplete concrete WikiI of AbstractWiki = open Syntax in {
  lincat
    Entity = NP ; Property = AP ; Fact = S ; 
    Predicate = VP ; Modifier = Adv ; Value = {s : Str} ;

  lin
    mkFact entity predicate = mkS (mkCl entity predicate) ;
    mkIsAProperty entity property = mkS (mkCl entity (mkVP property)) ;
    FactWithMod fact modifier = mkS modifier fact ;

    Entity2NP e = e ;
    Property2AP p = p ;
    VP2Predicate p = p ;
}
