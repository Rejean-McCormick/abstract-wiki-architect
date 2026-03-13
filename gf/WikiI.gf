incomplete concrete WikiI of SemantikArchitect = open Prelude in {

  lincat
    Statement   = SS ;
    Entity      = SS ;
    Profession  = SS ;
    Nationality = SS ;
    EventObj    = SS ;

  lin
    mkEntityStr s = s ;
    strProf s     = s ;
    strNat s      = s ;
    strEvent s    = s ;

    mkBioProf e p   = ss (e.s ++ "is a" ++ p.s) ;
    mkBioNat  e n   = ss (e.s ++ "is" ++ n.s) ;
    mkBioFull e p n = ss (e.s ++ "is a" ++ n.s ++ p.s) ;
    mkEvent e ev    = ss (e.s ++ "participated in" ++ ev.s) ;
}