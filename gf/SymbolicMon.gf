
resource SymbolicMon = open Syntax, ParadigmsMon, NounMon in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
