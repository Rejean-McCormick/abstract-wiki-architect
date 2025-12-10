
resource SymbolicHin = open Syntax, ParadigmsHin, NounHin in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
