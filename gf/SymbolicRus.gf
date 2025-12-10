
resource SymbolicRus = open Syntax, ParadigmsRus, NounRus in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
