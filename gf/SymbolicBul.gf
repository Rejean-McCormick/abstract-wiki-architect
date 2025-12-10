
resource SymbolicBul = open Syntax, ParadigmsBul, NounBul in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
