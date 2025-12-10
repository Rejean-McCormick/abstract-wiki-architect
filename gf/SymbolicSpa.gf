
resource SymbolicSpa = open Syntax, ParadigmsSpa, NounSpa in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
