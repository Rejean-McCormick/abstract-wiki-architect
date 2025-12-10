
resource SymbolicNor = open Syntax, ParadigmsNor, NounNor in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
