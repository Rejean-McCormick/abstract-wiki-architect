
resource SymbolicSwe = open Syntax, ParadigmsSwe, NounSwe in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
