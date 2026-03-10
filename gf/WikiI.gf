incomplete concrete WikiI of SemantikArchitect = open Prelude, Syntax, Symbolic in {

  lincat
    Statement   = S ;
    Entity      = NP ;
    Profession  = CN ;
    Nationality = AP ;
    EventObj    = NP ;

  lin
    mkEntityStr s = symb s ;
    strProf s     = mkCN (mkN s) ;
    strNat s      = mkAP (mkA s) ;
    strEvent s    = symb s ;

    mkBioProf e p   = mkS (mkCl e p) ;
    mkBioNat  e n   = mkS (mkCl e n) ;
    mkBioFull e p n = mkS (mkCl e (mkCN n p)) ;
    mkEvent e ev    = mkS (mkCl e ev) ;
}