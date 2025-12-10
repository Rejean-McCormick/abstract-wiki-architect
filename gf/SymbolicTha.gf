
resource SymbolicTha = open Syntax, ParadigmsTha, NounTha in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
