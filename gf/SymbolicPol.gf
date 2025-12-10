
resource SymbolicPol = open Syntax, ParadigmsPol, NounPol in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
