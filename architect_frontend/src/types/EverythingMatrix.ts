/**
 * The Root Object for the Everything Matrix
 * Matches data/indices/everything_matrix.json
 */
export interface EverythingMatrix {
  timestamp: string; // ISO Date String
  languages: Record<string, LanguageEntry>;
}

/**
 * Represents a single Language in the Matrix
 */
export interface LanguageEntry {
  meta: LanguageMeta;
  blocks: LanguageBlocks;
  status: LanguageStatus;
}

/**
 * Metadata about the language identity
 */
export interface LanguageMeta {
  wiki_code: string; // e.g. "Eng"
  rgl_code: string;  // e.g. "Eng" (usually same)
  iso_code: string;  // e.g. "en"
  name: string;      // e.g. "English"
  family?: string;   // e.g. "Germanic"
}

/**
 * The 15 Architectural Blocks (scored 0-10)
 */
export interface LanguageBlocks {
  // --- ZONE A: RGL FOUNDATION ---
  rgl_cat: number;       // Category definitions (CatX.gf)
  rgl_noun: number;      // Noun morphology (NounX.gf)
  rgl_paradigms: number; // Constructors (ParadigmsX.gf)
  rgl_grammar: number;   // Structural Grammar (GrammarX.gf)
  rgl_syntax: number;    // High-Level API (SyntaxX)

  // --- ZONE B: LEXICON ---
  lex_seed: number;      // AI/Bootstrap Dictionary (data/seeds)
  lex_concrete: number;  // Compiled GF Dictionary (WikiX.gf)
  lex_wide: number;      // Large Import (Wiktionary/PanLex)
  sem_mappings: number;  // Abstract->Concrete Semantic Maps

  // --- ZONE C: APPLICATION ---
  app_profile: number;   // Frontend Config (profiles.json)
  app_assets: number;    // UI Assets (Flags)
  app_routes: number;    // Backend API Logic

  // --- ZONE D: QUALITY ---
  build_config: number;  // Strategy Assigned (High/Safe)
  meta_compile: number;  // Binary Compilation (Wiki.pgf)
  meta_test: number;     // Unit Test Pass Rate
}

/**
 * High-level status and calculated maturity
 */
export interface LanguageStatus {
  build_strategy: 'HIGH_ROAD' | 'SAFE_MODE' | 'BROKEN' | 'SKIP' | 'NOT_INSTALLED' | 'NONE' | string;
  overall_maturity: number; // 0.0 to 10.0
  is_active: boolean;       // True if compiled and usable
}