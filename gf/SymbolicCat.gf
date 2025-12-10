
resource SymbolicCat = open Syntax, ParadigmsCat, NounCat in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
