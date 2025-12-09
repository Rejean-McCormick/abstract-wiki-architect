incomplete concrete WikiI of AbstractWiki = open Syntax in {
  lincat Entity = NP; Property = AP; Fact = S; Predicate = VP; Modifier = Adv; Value = {s : Str};
  lin
    mkFact s p = mkS (mkCl s p);
    mkIsAProperty s p = mkS (mkCl s (mkVP p));
    FactWithMod f m = mkS m f;
    Entity2NP x = x; Property2AP x = x; VP2Predicate x = x;
}
