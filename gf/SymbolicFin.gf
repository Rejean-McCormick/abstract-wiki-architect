
resource SymbolicFin = open Syntax, ParadigmsFin, NounFin in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
