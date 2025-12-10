
resource SymbolicTur = open Syntax, ParadigmsTur, NounTur in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
