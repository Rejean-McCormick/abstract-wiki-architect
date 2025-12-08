abstract AbstractWiki = {
  cat
    Entity ; Property ; Fact ; Predicate ; Modifier ; Value ;

  fun
    mkFact : Entity -> Predicate -> Fact ;
    mkIsAProperty : Entity -> Property -> Fact ;
    FactWithMod : Fact -> Modifier -> Fact ;
    mkLiteral : Value -> Entity ;

    Entity2NP : Entity -> Entity ;
    Property2AP : Property -> Property ;
    VP2Predicate : Predicate -> Predicate ;

    -- Vocabulary
    animal_Entity : Entity ;
}
