
resource SymbolicJap = open Syntax, ParadigmsJpn, NounJpn in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
