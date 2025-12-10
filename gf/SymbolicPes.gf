
resource SymbolicPes = open Syntax, ParadigmsPes, NounPes in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
