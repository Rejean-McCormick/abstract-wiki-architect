Here is the updated **`docs/15-SCHEMA_ALIGNMENT_PROTOCOL.md`**.

This version incorporates the **v2.1 Overloading Strategy** (handling partial data via `mkBioFull`/`mkBioProf`) and the **WordNet/RGL integration** defined in your architecture specifications.

---

# 📐 Schema Alignment Protocol & The "Triangle of Doom"

**SemantiK Architect v2.1**

## 1. The Core Problem: Alignment Failure

In the v2.1 architecture, a runtime error (`400 Bad Request` or `Function not found`) often occurs not because code is broken, but because the system's three definitions of "Truth" are out of sync.

We call this the **Triangle of Doom**:

1. **The API Contract (Input):** What the user sends (JSON). Defined in `schemas/*.json` and `app/adapters/ninai.py`.
2. **The Abstract Grammar (Interface):** What the engine accepts (GF). Defined in `gf/semantik_architect.gf`.
3. **The Factory Logic (Generator):** What the builder produces (Python). Defined in `utils/grammar_factory.py`.

### The Symptom

* **Error:** `Function 'mkBio' not found in grammar` or `unknown function` in compiler logs.
* **Cause:** The API sent a `frame_type="bio"` (expecting `mkBio`), but the Abstract Grammar only defined `mkFact` or required different arguments.

---

## 2. The Solution: Manual Propagation Protocol

Until a "Schema-to-Grammar" compiler is built, we explicitly adopt a **Manual Propagation Strategy**. To add or fix a Semantic Frame (e.g., `Event`, `Bio`, `Location`), you **MUST** update all three vertices of the triangle simultaneously.

### Step 1: Update the Interface (Abstract Grammar)

**File:** `gf/semantik_architect.gf`

Define the function signature. **v2.1 Mandate:** Use **Overloading** to handle missing data (e.g., when a user provides a Profession but no Nationality).

```haskell
cat Statement ; Entity ; Profession ; Nationality ;
fun
  -- The "Perfect" Case (All data available)
  mkBioFull : Entity -> Profession -> Nationality -> Statement ;

  -- The "Partial" Cases (Graceful Degradation)
  mkBioProf : Entity -> Profession -> Statement ;
  mkBioNat  : Entity -> Nationality -> Statement ;

  -- Type Coercion (Bridge from WordNet types)
  lexProf : N -> Profession ;
  lexNat  : A -> Nationality ;

```

### Step 2: Update the Factory (Tier 3 Generation)

**File:** `utils/grammar_factory.py`

Teach the "Safe Mode" generator how to linearize these new functions for under-resourced languages (Tier 3). Since Tier 3 lacks the RGL's full power, we use **Weighted Topology** or simple concatenation stubs.

```python
def generate_safe_mode_grammar(lang_code):
    # ...
    gf_code = f"""
    lin
      -- Tier 3 Stubs (Strings)
      mkBioFull name prof nat = name ++ "is a" ++ nat ++ prof;
      mkBioProf name prof     = name ++ "is a" ++ prof;
      
      -- Coercion Stubs
      lexProf n = n;
      lexNat n = n;
    """

```

### Step 3: Update Tier 1 Concrete Grammars

**File:** `gf/WikiEng.gf` (and other RGL languages)

For High-Resource languages, you must link the **Abstract** functions to the **Concrete** RGL logic and the **WordNet** lexicon.

```haskell
concrete WikiEng of SemantikArchitect = open SyntaxEng, ParadigmsEng, WordNetEng in {
  lincat 
    Statement = S ; 
    Profession = CN ; 
    Nationality = AP ;

  lin
    -- Use RGL macros (mkS, mkCl, mkVP) for grammatically correct output
    mkBioFull s p n = mkS (mkCl s (mkVP n p)) ;  -- "He is an American physicist"
    mkBioProf s p   = mkS (mkCl s (mkVP (mkCN p))) ; -- "He is a physicist"

    -- Coercion
    lexProf n = mkCN n ;
}

```

---

## 3. Decision Record (ADR)

### Context

The API layer (`NinaiAdapter`) is dynamic and handles optional JSON fields. The Grammar layer (`GF`) is static, strictly typed, and requires fixed arity (argument counts).

### Decision

We choose **Explicit Semantic Mapping** with **Overloading** over **Generic Triples**.

* **Option A (Rejected):** Use a generic `mkTriple : Subject -> Predicate -> Object -> Fact` for everything.
* *Pros:* No need to update grammar for new frames.
* *Cons:* Loses semantic nuance (e.g., "Born in" vs "Located in") required for accurate translations and UD tagging.


* **Option B (Accepted):** Define specific functions `mkBioFull`, `mkBioProf`.
* *Pros:* Allows language-specific handling (e.g., French uses "né en" for birth, "situé à" for location) and handles missing data gracefully.
* *Cons:* Requires the 3-step manual update process described above.



### Future Roadmap

To automate this, we will eventually implement an **Abstract Generator** script that reads `schemas/frames/*.json` and auto-generates `semantik_architect.gf` during the build pre-flight check.