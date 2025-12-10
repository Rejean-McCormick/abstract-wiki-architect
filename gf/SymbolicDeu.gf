
resource SymbolicDeu = open Syntax, ParadigmsGer, NounGer in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
