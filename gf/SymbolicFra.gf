
resource SymbolicFra = open Syntax, ParadigmsFre, NounFre in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
