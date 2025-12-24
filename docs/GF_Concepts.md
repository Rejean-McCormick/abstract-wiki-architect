# Grammatical Framework (GF): Core Concepts & Compilation

## 1. The Compilation Process (`gf -make`)

When we run the command `gf -make`, we are transforming human-readable source code into a machine-optimized format. This process acts like a funnel, merging logic, rules, and vocabulary into a single executable brain.

### The Source (Inputs)
We start with three distinct types of `.gf` source files:
* **The Logic (`AbstractWiki.gf`):** The "Blueprint". It defines *what* can be said (semantics), such as `mkBio` taking an Entity and a Profession. It contains no language-specific words, only mathematical structure.
* **The Rules (`WikiEng.gf`):** The "Translator". It implements the blueprint for a specific language (English), defining word order, agreement, and syntax.
* **The Vocabulary (`WikiLexiconEng.gf`):** The "Dictionary". It provides the raw words (strings) that plug into the grammar.

### The Action (Compilation)
The compiler acts as a processor. It parses all source files, validates them for logical consistency (type checking), and merges them. It ensures that every function defined in the Abstract grammar is correctly implemented in the Concrete grammar.

### The Destination (Output)
The result is a single binary file: **`Wiki.pgf`**.
* **Binary:** It is optimized for machines, not humans.
* **Fast:** It is designed to be loaded instantly into memory (RAM).

---

## 2. The Portable Grammar Format (PGF)

**PGF** stands for **Portable Grammar Format**. It is the standard executable format for the GF ecosystem, analogous to Java Bytecode or a compiled binary.

### Why PGF?
1.  **Portable:** A single `.pgf` file can be run on any platform—Python, C, Android, or JavaScript runtimes.
2.  **Multilingual:** A single `.pgf` file contains *all* compiled languages (English, French, Russian, etc.). This allows the runtime to switch between languages instantly or translate between them without losing meaning.
3.  **Efficiency:** Because the grammar is pre-compiled into a mathematical graph, the runtime engine does not need to parse text files. It performs generation and parsing operations in milliseconds.

---

## 3. The "Pivot" Concept

A common misconception is that English serves as the central translation language. In GF, **English is not the pivot.**

### The Abstract Syntax Tree (AST)
The true pivot is the **Abstract Grammar**.
* **Abstract:** $mkBio(Q42, Physicist)$
* **Concrete (English):** "Douglas Adams is a physicist"
* **Concrete (French):** "Douglas Adams est un physicien"

The system does not translate *English $\rightarrow$ French*. Instead, it parses English into the language-neutral **Abstract** structure, and then linearizes that Abstract structure into French. This ensures that the underlying semantic meaning remains pure, regardless of the surface language.

```

### Pour l'ajouter rapidement via votre terminal :

Vous pouvez copier-coller cette commande dans votre terminal WSL pour créer le fichier d'un coup :

```bash
cat <<EOF > doc/GF_Concepts.md
# Grammatical Framework (GF): Core Concepts & Compilation

## 1. The Compilation Process ('gf -make')
When we run the command 'gf -make', we are transforming human-readable source code into a machine-optimized format.

### The Source (Inputs)
* **The Logic (Abstract):** The Blueprint. Defines *what* can be said.
* **The Rules (Concrete):** The Translator. Defines grammar rules (English).
* **The Vocabulary (Lexicon):** The Dictionary. Raw words.

### The Action (Compilation)
The compiler merges these files, validating logical consistency and type safety.

### The Destination (Output)
The result is a single binary file: **Wiki.pgf**. It is machine-optimized for instant loading into RAM.

---

## 2. The Portable Grammar Format (PGF)
PGF is the executable format for GF.
* **Portable:** Runs on Python, C, JS, Android.
* **Multilingual:** Contains ALL languages in one file.
* **Efficient:** Binary format allows millisecond generation.

---

## 3. The "Pivot" Concept
**English is not the pivot.** The pivot is the **Abstract Grammar**.
The system translates via the language-neutral Abstract Syntax Tree (AST), not by translating English to French directly.
EOF

```