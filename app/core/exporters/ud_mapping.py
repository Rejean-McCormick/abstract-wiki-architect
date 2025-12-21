"""
app/core/exporters/ud_mapping.py

The Frozen Ledger for Construction-Time UD Tagging.
This maps Grammatical Framework (RGL) Constructor functions to their
corresponding Universal Dependencies (CoNLL-U) roles.

Used by the UDExporter to generate tagged datasets for evaluation.
Ref: docs/10-STANDARDS_ALIGNMENT.md
"""

from typing import Dict

# --- Universal Dependencies v2 Standard Tags ---
TAG_ROOT = "root"
TAG_NSUBJ = "nsubj"
TAG_OBJ = "obj"
TAG_IOBJ = "iobj"
TAG_DET = "det"
TAG_AMOD = "amod"  # Adjectival Modifier
TAG_ADV = "advmod"
TAG_COP = "cop"    # Copula (is, was)
TAG_PUNCT = "punct"
TAG_DEP = "dep"    # Fallback

# --- RGL Signature Map ---
# Format: "RGL_Function_Name": { Arg_Index: UD_Tag }
# Indices correspond to the order arguments are passed in the GF Abstract Syntax.

RGL_SIGNATURES: Dict[str, Dict[int, str]] = {
    # --------------------------------------------------------------------------
    # CLAUSE CONSTRUCTORS (Sentence Level)
    # --------------------------------------------------------------------------
    
    # mkCl (Subject, Verb) -> "John sleeps"
    "mkCl_SV": {
        0: TAG_NSUBJ,  # Arg 0: Subject
        1: TAG_ROOT    # Arg 1: Verb
    },

    # mkCl (Subject, Verb, Object) -> "John eats apples"
    "mkCl_SVO": {
        0: TAG_NSUBJ,
        1: TAG_ROOT,
        2: TAG_OBJ
    },
    
    # mkCl (Subject, Copula, Complement) -> "John is a doctor"
    # NOTE: In UD, the *Complement* is the ROOT, and the Copula is a dependent 'cop'.
    # But RGL often hides the copula in the function name.
    "mkCl_SC": {
        0: TAG_NSUBJ,
        1: TAG_ROOT   # The Predicate (Noun/Adj) is the structural root
    },
    
    # --------------------------------------------------------------------------
    # NOUN PHRASE CONSTRUCTORS
    # --------------------------------------------------------------------------
    
    # mkNP (Determiner, CommonNoun) -> "the car"
    "mkNP_DetCN": {
        0: TAG_DET,
        1: TAG_ROOT   # The Noun is the head of the phrase
    },
    
    # mkCN (Adjective, CommonNoun) -> "red car"
    "mkCN_AdjCN": {
        0: TAG_AMOD,
        1: TAG_ROOT
    }
}

def get_ud_role(function_name: str, arg_index: int) -> str:
    """
    Retrieves the UD tag for a specific argument of an RGL function.
    
    Args:
        function_name: The internal RGL function (e.g., 'mkCl_SVO').
        arg_index: The 0-based index of the argument being processed.
        
    Returns:
        The CoNLL-U tag (e.g., 'nsubj'). Defaults to 'dep' if unknown.
    """
    signature = RGL_SIGNATURES.get(function_name)
    if signature:
        return signature.get(arg_index, TAG_DEP)
    return TAG_DEP