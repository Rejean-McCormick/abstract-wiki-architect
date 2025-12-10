
resource SymbolicEng = open Syntax, ParadigmsEng, NounEng in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
