
resource SymbolicLat = open Syntax, ParadigmsLat, NounLat in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
