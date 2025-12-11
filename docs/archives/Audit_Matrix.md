# Technical Specification: RGL Audit Matrix

## 1\. Overview

The **RGL Audit Matrix** is a consolidated data table that acts as the "Source of Truth" for the build orchestrator. Its purpose is to eliminate guesswork by explicitly validating the presence of critical Grammatical Framework (GF) modules for every target language *before* code generation begins.

It solves the "Impedance Mismatch" by categorizing languages into architectural types (Standard vs. Functor) based on verified file system evidence rather than assumptions.

-----

## 2\. Input Data Sources

The matrix aggregates data from three primary inputs:

1.  **Language Map (`rgl_map.json`)**: Provides the translation key between external ISO-like codes (e.g., `Bas`) and internal RGL codes (e.g., `Eus`).
2.  **Path Index (`rgl_paths.json`)**: Provides the specific file system locations for confirmed RGL modules.
3.  **File System (RGL Source Tree)**: A live scan of the `gf-rgl/src` directory to verify the physical existence of required `.gf` files.

-----

## 3\. Matrix Schema (Columns)

The Audit Matrix contains **9 core columns**. Each row represents one target language.

| Column Name | Description | Source | Example Value |
| :--- | :--- | :--- | :--- |
| **Wiki Code** | The 3-letter code used in our project's Abstract Wiki. | `rgl_map.json` | `Eng`, `Cat` |
| **RGL Code** | The internal 3-letter code used by the GF library. | `rgl_map.json` | `Eng`, `Cat` |
| **Path** | The relative directory of the language within `gf-rgl/src`. | `rgl_paths.json` | `english`, `catalan` |
| **Cat** | Status of the Category module (`CatX.gf`). | File Scan | `VALIDATED`, `ABSENT` |
| **Noun** | Status of the Noun/Morphology module (`NounX.gf`). | File Scan | `VALIDATED`, `ABSENT` |
| **Paradigms** | Status of the Paradigms module (`ParadigmsX.gf`). | File Scan | `VALIDATED`, `ABSENT` |
| **Grammar** | Status of the main Grammar module (`GrammarX.gf`). | File Scan | `VALIDATED`, `ABSENT` |
| **Syntax** | Status of the High-Level API module (`SyntaxX`). | Derived | `VALIDATED`, `ABSENT` |
| **Strategy** | The determined build strategy for this language. | Calculated | `HIGH_ROAD`, `SAFE_MODE` |

-----

## 4\. Module Validation States

For columns **Cat**, **Noun**, **Paradigms**, and **Grammar**, the system assigns one of the following states based on physical file verification:

  * **VALIDATED**: The file physically exists at the constructed path (e.g., `.../src/english/GrammarEng.gf`).
  * **ABSENT**: The file does not exist at the expected location.
  * **VIRTUAL** (Internal Logic Only): The module is known to exist conceptually (e.g., via inheritance) but has no physical file. For the purpose of the Audit Matrix, this is treated as `ABSENT` because the simple file checker cannot see it.

-----

## 5\. Classification Logic (The "Strategy" Column)

This is the core intelligence of the matrix. The orchestrator uses the presence/absence of modules to assign one of three compilation strategies:

### **Strategy A: HIGH\_ROAD (Standard)**

  * **Definition:** The language supports the full, high-level RGL API, including complex syntax constructors (`mkNP`, `mkS`).
  * **Criteria:**
      * `Cat` = **VALIDATED**
      * `Noun` = **VALIDATED**
      * `Paradigms` = **VALIDATED**
      * `Grammar` = **VALIDATED** (Critical Differentiator)
  * **Implication for Builder:** The script will import `GrammarX` and use `SyntaxX` constructors.
  * **Typical Languages:** English (`Eng`), German (`Ger`), French (`Fre`).

### **Strategy B: SAFE\_MODE (Functor/Partial)**

  * **Definition:** The language lacks a physical `Grammar` file (likely a Functor instantiation) or has a broken Syntax path, but possesses valid Dictionary and Category definitions.
  * **Criteria:**
      * `Cat` = **VALIDATED**
      * `Noun` = **VALIDATED**
      * `Paradigms` = **VALIDATED**
      * `Grammar` = **ABSENT**
  * **Implication for Builder:** The script will **bypass** `GrammarX`/`SyntaxX` and link directly to `NounX` and `CatX`. It will use low-level constructors (`MassNP`, `UsePN`) to guarantee compilation safety.
  * **Typical Languages:** Catalan (`Cat`), Danish (`Dan`), Afrikaans (`Afr`).

### **Strategy C: BROKEN (Skip)**

  * **Definition:** The language is missing fundamental building blocks required for any compilation.
  * **Criteria:**
      * `Cat` = **ABSENT** OR `Noun` = **ABSENT**
  * **Implication for Builder:** The language is explicitly added to the Skip List.
  * **Typical Languages:** (Potentially) Amharic (`Amh`), Ancient Greek (`Grc`).

-----

## 6\. Output Artifact

The process generates a single CSV file named **`rgl_audit_matrix.csv`**.

**Example Row (High Road):**

```csv
Eng,Eng,english,VALIDATED,VALIDATED,VALIDATED,VALIDATED,VALIDATED,HIGH_ROAD
```

**Example Row (Safe Mode):**

```csv
Cat,Cat,catalan,VALIDATED,VALIDATED,VALIDATED,ABSENT,ABSENT,SAFE_MODE
```