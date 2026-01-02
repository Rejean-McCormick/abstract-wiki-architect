concrete WikiMay of AbstractWiki = open Prelude in {
  lincat
    Statement = SS;
    Entity = SS;
    Profession = SS;
    Nationality = SS;
    EventObj = SS;

  lin
    -- Dynamic Topology: ms (SVO)

    -- 1. Wrappers (Pass-through because input is already SS)
    mkEntityStr s = s;
    strProf s = s;
    strNat s = s;
    strEvent s = s;
    
    -- 2. Bio Frames (Wrap the constructed string)
    mkBioProf entity prof = ss (entity.s ++ "is a" ++ prof.s);
    mkBioNat entity nat = ss (entity.s ++ "is" ++ nat.s);
    mkBioFull entity prof nat = ss (entity.s ++ "is a" ++ nat.s ++ prof.s);

    -- 3. Event Frames
    mkEvent entity event = ss (entity.s ++ "participated in" ++ event.s);

}
