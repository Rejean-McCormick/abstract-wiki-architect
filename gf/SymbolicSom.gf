
resource SymbolicSom = open Syntax, ParadigmsSom, NounSom in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
