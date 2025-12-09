abstract AbstractWiki = {
  cat Entity; Property; Fact; Predicate; Modifier; Value;
  fun
    mkFact : Entity -> Predicate -> Fact;
    mkIsAProperty : Entity -> Property -> Fact;
    FactWithMod : Fact -> Modifier -> Fact;
    mkLiteral : Value -> Entity;
    Entity2NP : Entity -> Entity; Property2AP : Property -> Property; VP2Predicate : Predicate -> Predicate;
    lex_animal_N : Entity; lex_walk_V : Predicate; lex_blue_A : Property;
}
