
resource SymbolicLit = open Syntax, ParadigmsLit, NounLit in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
