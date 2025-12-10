
resource SymbolicHeb = open Syntax, ParadigmsHeb in {
  oper
    -- Use the universally supported Proper Name construction to create NP from Str
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
