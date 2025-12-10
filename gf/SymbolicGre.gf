
resource SymbolicGre = open Syntax, ParadigmsGre, NounGre in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
