concrete WikiSwa of Wiki = CatSwa, NounSwa ** open NounSwa, (P = ParadigmsSwa) in {
  lin
    -- Fallback: Use MassNP or DetCN if mkNP is unavailable
    SimpNP cn = MassNP cn ;
    
    -- Fallback: UsePN promotes a Proper Name to an NP
    John = UsePN (P.mkPN "John") ; 
    
    Here = P.mkAdv "here" ;
    
    -- Fallback: UseN promotes a Noun to a Common Noun
    apple_N = UseN (P.mkN "apple") ;
}