
resource SymbolicChi = open Syntax, ParadigmsChi, NounChi in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
