
resource SymbolicSlv = open Syntax, ParadigmsSlo, NounSlo in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
