
resource SymbolicIta = open Syntax, ParadigmsIta, NounIta in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
