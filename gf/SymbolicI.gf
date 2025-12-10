
resource SymbolicI = open Prelude, SyntaxI in {
  oper
    symb : Str -> NP = \s -> 
      lin NP { s = \c -> s ; a = agrP3 Sg } ; -- Minimal stub
}
