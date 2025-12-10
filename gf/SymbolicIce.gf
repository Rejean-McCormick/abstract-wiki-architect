
resource SymbolicIce = open Syntax, ParadigmsIce, NounIce in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
