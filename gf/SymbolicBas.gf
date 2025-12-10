
resource SymbolicBas = open Syntax, ParadigmsEus, NounEus in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
