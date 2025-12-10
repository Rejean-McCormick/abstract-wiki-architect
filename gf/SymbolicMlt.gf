
resource SymbolicMlt = open Syntax, ParadigmsMlt, NounMlt in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
