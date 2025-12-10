
resource SymbolicPor = open Syntax, ParadigmsPor, NounPor in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
