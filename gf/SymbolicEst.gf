
resource SymbolicEst = open Syntax, ParadigmsEst, NounEst in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
