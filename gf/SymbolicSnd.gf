
resource SymbolicSnd = open Syntax, ParadigmsSnd, NounSnd in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
