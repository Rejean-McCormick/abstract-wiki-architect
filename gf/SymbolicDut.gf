
resource SymbolicDut = open Syntax, ParadigmsDut, NounDut in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
