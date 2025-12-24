concrete WikiAra of AbstractWiki = open Prelude in {
  lincat
    Entity = Str;
    Frame = Str;
    Property = Str;
    Fact = Str;
    Predicate = Str;
    Modifier = Str;
    Value = Str;

  lin
    -- Dynamic Topology for ara (VSO)
    
    -- Core Semantics
    mkFact subj pred = pred ++ subj;
    
    -- Hardcoded stub for 'is a property'
    mkIsAProperty subj prop = "is" ++ subj ++ prop;

    -- Specialized Frames (Schema Alignment)
    -- Bio: Name -> Profession -> Nationality -> Fact
    mkBio name prof nat = "is a" ++ name ++ nat ++ prof;

    -- Event: Subject -> EventObject -> Fact
    mkEvent subject event = "participated in" ++ subject ++ event;
    
    -- Modifiers
    FactWithMod fact mod = fact ++ mod;
    
    -- Lexical Stubs
    mkLiteral s = s;
    
    -- Type Converters
    Entity2NP e = e;
    Property2AP p = p;
    VP2Predicate p = p;

    -- Required Lexicon Stubs
    lex_animal_N = "animal";
    lex_walk_V = "walks";
    lex_blue_A = "blue";
}
