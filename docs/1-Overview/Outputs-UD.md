# 14. Outputs: UD

SemantiK Architect can optionally output **Universal Dependencies (UD)** as a **CoNLL-U-style** representation of the generated sentence, alongside the normal surface text.  

## What this output is

* A **dependency-grammar view** of the same sentence you just generated (token-level structure and relations), produced by the **UD Exporter / UD Mapping** component. 
* Conceptually, it’s an **“audit trail”**: a standardized linguistic structure you can compare across languages and against UD resources. 

## Why SemantiK Architect outputs UD

* **Evaluation & benchmarking:** the docs explicitly frame UD output as something you can evaluate “against treebanks.” 
* **Interoperability:** UD is treated as a standards layer (“Standards: UD Exporter (CoNLL-U Tag Mapping)”). 
* **Separation of concerns:** UD Mapping is a first-class *output port* alongside the text renderer (so you can use it without changing the core engine). 

## When you should use UD output

* When you want to **validate** that generation follows a consistent syntactic structure across languages.
* When you want a **language-agnostic diagnostic** view (useful when surface text quality varies due to tier/coverage).
* When building QA workflows where “text looks OK” is not enough and you want a structural signal.

## Important constraints (high level)

* UD output only works as well as the **mapping coverage**: every syntactic constructor needs a corresponding CoNLL-U mapping rule. 
* If a mapping is missing, UD export can fail (the API error table explicitly calls out “UD Exporter failed to map a function”). 
