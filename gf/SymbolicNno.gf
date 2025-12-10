
resource SymbolicNno = open Syntax, ParadigmsNno, NounNno in {
  oper
    symb : Str -> NP = \s -> mkNP (mkPN s) ; 
}
