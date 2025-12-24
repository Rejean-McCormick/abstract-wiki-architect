-- gf/WikiEng.gf
concrete WikiEng of AbstractWiki = WikiLexiconEng ** open SyntaxEng, ParadigmsEng, SymbolicEng, StructuralEng, Prelude, (R=ResEng) in { 

  lincat 
    Statement = S ; 
    Entity = NP ; 
    Profession = CN ; 
    Nationality = AP ; 
    EventObj = NP ; 

  -- === THE NUCLEAR TOOLS (With Type Casting) ===
  oper
    robustName : Str -> NP = \s -> lin NP {
      s = \\c => s ;          
      a = R.AgP3Sg R.Neutr ;  
    } ;

    robustCommon : Str -> CN = \s -> lin CN {
      s = \\n,c => s ;        
      g = R.Neutr ;           
    } ;

    robustAdj : Str -> AP = \s -> lin AP {
      s = \\f => s ;          
      isPre = True ;          
    } ;

  lin 
    mkEntity pn = mkNP pn ;
    mkEntityStr s = robustName s.s ; 

    mkBioFull s p n = mkS (mkCl s (mkVP (mkCN n p))) ;      
    mkBioProf s p   = mkS (mkCl s (mkVP (mkNP a_Det p))) ; 
    mkBioNat  s n   = mkS (mkCl s (mkVP n)) ;        
    mkEvent   s e   = mkS (mkCl s (mkVP (mkV2 (mkV "participate") in_Prep) e)) ;

    lexProf n = mkCN n ; 
    lexNat  a = mkAP a ; 
    lexEvent n = mkNP (mkCN n) ; 

    strProf s  = robustCommon s.s ; 
    strNat  s  = robustAdj s.s ; 
    strEvent s = robustName s.s ; 
}
