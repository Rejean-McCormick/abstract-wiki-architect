concrete WikiSnd of AbstractWiki = open Prelude in {
  lincat
    Entity = Str;
    Frame = Str;
    Property = Str;
    Fact = Str;
    Predicate = Str;
    Modifier = Str;
    Value = Str;

  lin
    -- Dynamic Topology for snd (SVO)
    
    -- Core Semantics
    mkFact subj pred = subj ++ pred;
    
    -- Hardcoded stub for 'is a property'
    mkIsAProperty subj prop = subj ++ "is" ++ prop;

    -- Specialized Frames (Schema Alignment)
    -- Bio: Name -> Profession -> Nationality -> Fact
    mkBio name prof nat = name ++ "is a" ++ nat ++ prof;

    -- Event: Subject -> EventObject -> Fact
    mkEvent subject event = subject ++ "participated in" ++ event;
    
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
