
resource SymbolicRom = open Syntax, ParadigmsRon, NounRon in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
