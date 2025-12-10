
resource SymbolicUrd = open Syntax, ParadigmsUrd, NounUrd in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
