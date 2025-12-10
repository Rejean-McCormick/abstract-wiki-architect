
resource SymbolicLav = open Syntax, ParadigmsLav, NounLav in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
