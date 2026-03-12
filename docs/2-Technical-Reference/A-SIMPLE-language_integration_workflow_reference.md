**Language Integration Workflow**  
Quick Reference

Purpose: the clean normal path to integrate one language without getting lost in the toolchain.

| Core rule: add or change files first, then refresh the Everything Matrix. The matrix is the system snapshot, not the source of edits. |
| :---- |

# **Normal workflow**

## **1\. Add language files**

Put the language grammar, config, and lexicon files in place. Do not compile yet.

## **2\. Refresh the Everything Matrix**

Make the system discover the new or changed language and update strategy/status.

## **3\. Validate the lexicon**

Check that the language data is structurally usable before build.

## **4\. Compile the PGF**

Build the language into the grammar binary.

## **5\. Validate compile \+ runtime**

Confirm both build status and API generation status.

## **6\. Generate one real sentence**

Use the dev smoke test or the generation endpoint and verify you get text back.

## **7\. Stabilize (optional)**

Run judge/regression checks, then refresh the matrix again so the final build/test state is recorded.

# **Exact tool calls**

| Step | Command |
| :---- | :---- |
| Refresh matrix | build\_index \--langs \<lang\> \--regen-rgl \--regen-lex \--regen-app  \--regen-qa \--verbose |
| Validate lexicon | lexicon\_coverage \--lang \<lang\> \--include-files |
| Compile PGF | compile\_pgf \--langs \<lang\> \--verbose |
| Validate health | language\_health \--mode both \--langs \<lang\> \--json \--verbose |
| Generate sentence | Use Dev smoke test or call /api/v1/generate/\<lang\> |
| Optional stabilization | run\_judge ...   then   build\_index ... again |

# **Required vs optional**

| Required in the normal path | Use only when needed |
| :---- | :---- |
| build\_index | run\_judge (stabilization) |
| lexicon\_coverage | harvest\_lexicon / gap\_filler (thin lexicon) |
| compile\_pgf | bootstrap\_tier1 (missing scaffolding) |
| language\_health | diagnostic\_audit (weird repo/build state) |
| one real generation test |  |

# **Dependencies to remember**

* Use ISO-2 language codes in tool calls, for example en, fr, pt.  
* Refresh the matrix after file changes, because compile/build strategy depends on that snapshot.  
* Validate the lexicon before compile, so bad or empty shards are caught early.  
* Compile before final health validation, so runtime results are not reading stale binaries.  
* A language is only truly integrated when it generates a sentence.