
resource SymbolicNep = open Syntax, ParadigmsNep, NounNep in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
