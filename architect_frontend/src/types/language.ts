// architect_frontend/src/types/language.ts

export interface Language {
  /**
   * The ISO 639-3 code (e.g., "eng", "zul", "kor").
   * This is the primary identifier used by the GF backend.
   */
  code: string;

  /**
   * The display name of the language (e.g., "English", "Zulu", "Korean").
   */
  name: string;

  /**
   * The Abstract Wikipedia Z-ID (e.g., "Z1002").
   * Useful for linking back to Wikifunctions or Wikidata.
   */
  z_id: string;
}