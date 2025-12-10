
resource SymbolicHun = open Syntax, ParadigmsHun, NounHun in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
