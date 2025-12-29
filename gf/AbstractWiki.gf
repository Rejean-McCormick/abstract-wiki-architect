abstract AbstractWiki = {

  flags startcat = Statement ;

  cat
    Statement ; 
    Entity ; 
    Profession ; 
    Nationality ; 
    EventObj ;

  fun
    -- 1. Entity Creators
    -- From RGL Proper Name (High Road)
    -- mkEntity : PN -> Entity ; 
    -- From Raw String (Safe Mode/LLM)
    mkEntityStr : String -> Entity ;

    -- 2. Biography Frames
    -- "Alan Turing is a British computer scientist"
    mkBioFull : Entity -> Profession -> Nationality -> Statement ;
    -- "Alan Turing is a computer scientist"
    mkBioProf : Entity -> Profession -> Statement ;
    -- "Alan Turing is British"
    mkBioNat : Entity -> Nationality -> Statement ;

    -- 3. Event Frames
    -- "Alan Turing participated in WWII"
    mkEvent : Entity -> EventObj -> Statement ;

    -- 4. Lexical Wrappers (Bridge to RGL or Raw Strings)
    -- lexProf : N -> Profession ;
    -- lexNat : A -> Nationality ;
    -- lexEvent : N -> EventObj ;
    
    strProf : String -> Profession ;
    strNat : String -> Nationality ;
    strEvent : String -> EventObj ;
}