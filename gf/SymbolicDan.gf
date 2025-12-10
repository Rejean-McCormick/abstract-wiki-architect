
resource SymbolicDan = open Syntax, ParadigmsDan, NounDan in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
