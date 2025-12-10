
resource SymbolicPan = open Syntax, ParadigmsPnb, NounPnb in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
