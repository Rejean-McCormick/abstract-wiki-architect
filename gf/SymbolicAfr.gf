
resource SymbolicAfr = open Syntax, ParadigmsAfr, NounAfr in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
