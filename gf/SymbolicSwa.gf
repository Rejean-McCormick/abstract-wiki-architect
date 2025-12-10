
resource SymbolicSwa = open Syntax, ParadigmsSwa, NounSwa in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
