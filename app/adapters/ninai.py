import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import ValidationError

from app.core.domain.frame import BioFrame, EventFrame, RelationalFrame
from app.shared.config import settings
# [FIX] Circular Import: Moved lexicon import inside methods to prevent startup crash
# from app.shared.lexicon import lexicon 

# Logger setup
logger = logging.getLogger(getattr(settings, "OTEL_SERVICE_NAME", "abstract-wiki"))

# --- CONSTANTS: The Ninai Protocol Ledger ---
CONSTRUCTOR_STATEMENT = "ninai.constructors.Statement"
CONSTRUCTOR_ENTITY = "ninai.constructors.Entity"
CONSTRUCTOR_LIST = "ninai.constructors.List"
TYPE_BIO = "ninai.types.Bio"
TYPE_EVENT = "ninai.types.Event"

class NinaiAdapter:
    """
    The Bridge between the external Ninai Protocol (Recursive JSON Objects)
    and the internal Abstract Wiki Architect Domain (Flat Pydantic Frames).
    v2.0 Upgrade: Integrates LexiconStore for Entity Grounding.
    """

    def parse(self, ninai_payload: Dict[str, Any], target_lang: str = "eng") -> Union[BioFrame, EventFrame, RelationalFrame]:
        """
        Main entry point. Recursively parses the input JSON tree.
        Now accepts 'target_lang' to resolve QIDs using the Lexicon.
        """
        # 1. Validate Root Structure
        func = ninai_payload.get("function")
        if func != CONSTRUCTOR_STATEMENT:
            raise ValueError(f"Invalid Root: Expected '{CONSTRUCTOR_STATEMENT}', got '{func}'")

        args = ninai_payload.get("args", [])
        if not args:
            raise ValueError("Invalid Statement: 'args' list is empty.")

        # 2. Extract Intent
        intent_obj = args[0]
        # CRITICAL FIX: Ninai stores the type in the 'function' key
        intent_type = intent_obj.get("function") 

        # 3. Route to specific handler
        if intent_type == TYPE_BIO:
            return self._parse_bio(args, target_lang)
        elif intent_type == TYPE_EVENT:
            return self._parse_event(args, target_lang)
        else:
            raise ValueError(f"Unsupported Ninai Type: {intent_type}")

    def _parse_bio(self, args: List[Dict[str, Any]], lang: str) -> BioFrame:
        """
        Parses a Biographical Statement.
        Enriches Entity data using the Lexicon (Zone B).
        """
        # [FIX] Local import to avoid circular dependency with app.shared.lexicon
        from app.shared.lexicon import lexicon

        try:
            # --- Subject (Arg 1) ---
            subject_node = args[1]
            subject_qid = self._extract_qid(subject_node)
            
            # Lookup in Lexicon (Enrichment)
            # FIXED: Use instance method
            subj_entry = lexicon.get_entry(lang, subject_qid) if subject_qid else None
            
            subject_name = self._extract_label(subject_node)
            subject_gender = None # Default to None if not found

            if subj_entry:
                # 1. Extract Name (Lemma)
                if subject_name == "Unknown":
                    subject_name = subj_entry.get("lemma", "Unknown") if isinstance(subj_entry, dict) else getattr(subj_entry, "lemma", "Unknown")
                
                # 2. Extract Gender (Critical for Tier 1 Languages)
                # Handle both Dict (JSON Shard) and Object (LexiconEntry) types
                if isinstance(subj_entry, dict):
                    subject_gender = subj_entry.get("features", {}).get("gender")
                elif hasattr(subj_entry, "features"):
                    subject_gender = subj_entry.features.get("gender")

            # --- Profession (Arg 2) ---
            # If the frame has a profession arg, use it. Otherwise try to auto-fill.
            profession_key = "person" # Default
            if len(args) > 2:
                prof_node = args[2]
                prof_qid = self._extract_qid(prof_node)
                prof_entry = lexicon.get_entry(lang, prof_qid) if prof_qid else None
                
                # [FIXED] Priority: GF Function -> Lemma -> Raw Value
                # This prevents "Q123" appearing in text when a lemma like "Physicist" is available.
                if prof_entry:
                    if isinstance(prof_entry, dict):
                         profession_key = prof_entry.get("gf_fun") or prof_entry.get("lemma")
                    else:
                         profession_key = getattr(prof_entry, "gf_fun", None) or getattr(prof_entry, "lemma", None)
                    
                    # If both are missing in the entry, fallback to extraction
                    if not profession_key:
                        profession_key = self._extract_value(prof_node)
                else:
                    profession_key = self._extract_value(prof_node)
            else:
                # Auto-fill from Subject P106
                # FIXED: Use local helper instead of assuming method exists on lexicon
                job_qids = self._get_lexicon_facts(lang, subject_qid, "P106")
                
                if job_qids:
                    # Try to resolve the first job QID to a GF function
                    job_entry = lexicon.get_entry(lang, job_qids[0])
                    if job_entry:
                         if isinstance(job_entry, dict):
                            profession_key = job_entry.get("gf_fun") or job_entry.get("lemma", "person")
                         else:
                            profession_key = getattr(job_entry, "gf_fun", None) or getattr(job_entry, "lemma", "person")

            # --- Nationality (Arg 3) ---
            nationality_key = None
            if len(args) > 3:
                nat_node = args[3]
                nat_qid = self._extract_qid(nat_node)
                nat_entry = lexicon.get_entry(lang, nat_qid) if nat_qid else None
                
                # [FIXED] Priority: GF Function -> Lemma -> Raw Value
                if nat_entry:
                    if isinstance(nat_entry, dict):
                        nationality_key = nat_entry.get("gf_fun") or nat_entry.get("lemma")
                    else:
                        nationality_key = getattr(nat_entry, "gf_fun", None) or getattr(nat_entry, "lemma", None)
                    
                    if not nationality_key:
                        nationality_key = self._extract_value(nat_node)
                else:
                    nationality_key = self._extract_value(nat_node)
            else:
                 # Auto-fill from Subject P27
                 # FIXED: Use local helper instead of assuming method exists on lexicon
                nat_qids = self._get_lexicon_facts(lang, subject_qid, "P27")
                
                if nat_qids:
                     # Try to resolve first nationality
                    nat_entry = lexicon.get_entry(lang, nat_qids[0])
                    if nat_entry:
                        if isinstance(nat_entry, dict):
                            nationality_key = nat_entry.get("gf_fun")
                        else:
                            nationality_key = getattr(nat_entry, "gf_fun", None)

            # --- Construct Frame ---
            # We inject the concrete GF function into 'meta' for the Engine to use
            meta_data = {}
            if subj_entry:
                gf_fun = subj_entry.get("gf_fun") if isinstance(subj_entry, dict) else getattr(subj_entry, "gf_fun", None)
                if gf_fun:
                    meta_data["subject_gf"] = gf_fun

            return BioFrame(
                frame_type="bio",
                subject={
                    "name": subject_name,
                    "qid": subject_qid,
                    "profession": profession_key,
                    "nationality": nationality_key,
                    "gender": subject_gender  # [FIX] Use resolved gender (m/f/n), not hardcoded "n"
                },
                context_id=subject_qid,
                meta=meta_data 
            )
        except IndexError:
            raise ValueError("Malformed BioFrame: Missing required arguments.")
        except ValidationError as e:
            raise ValueError(f"Validation Error in BioFrame: {e}")

    def _parse_event(self, args: List[Dict[str, Any]], lang: str) -> EventFrame:
        """
        Parses an Event Statement.
        """
        # [FIX] Local import to avoid circular dependency
        from app.shared.lexicon import lexicon

        try:
            # Subject
            subject_node = args[1]
            subject_qid = self._extract_qid(subject_node)
            subject_name = self._extract_label(subject_node)
            
            # Lexicon Lookup
            subj_entry = lexicon.get_entry(lang, subject_qid) if subject_qid else None
            
            if subject_name == "Unknown" and subj_entry:
                subject_name = subj_entry.get("lemma", "Unknown") if isinstance(subj_entry, dict) else getattr(subj_entry, "lemma", "Unknown")

            # Event Object
            event_node = args[2]
            event_name = self._extract_label(event_node)

            meta_data = {}
            if subj_entry:
                 gf_fun = subj_entry.get("gf_fun") if isinstance(subj_entry, dict) else getattr(subj_entry, "gf_fun", None)
                 if gf_fun:
                    meta_data["subject_gf"] = gf_fun

            return EventFrame(
                frame_type="event",
                subject={
                    "name": subject_name,
                    "qid": subject_qid
                },
                event_object=event_name,
                context_id=subject_qid,
                meta=meta_data
            )
        except IndexError:
            raise ValueError("Malformed EventFrame: Missing required arguments.")
        except ValidationError as e:
            raise ValueError(f"Validation Error in EventFrame: {e}")

    # --- Helper: Recursive Tree Walkers ---

    def _extract_label(self, node: Dict[str, Any]) -> str:
        """Extracts human-readable label or 'Unknown'."""
        if node.get("function") == CONSTRUCTOR_ENTITY:
            if len(node.get("args", [])) > 1:
                return node["args"][1]
        return "Unknown"

    def _extract_qid(self, node: Dict[str, Any]) -> Optional[str]:
        """Extracts the Wikidata ID (QID)."""
        if node.get("function") == CONSTRUCTOR_ENTITY:
            if len(node.get("args", [])) > 0:
                return node["args"][0]
        return None

    def _extract_value(self, node: Dict[str, Any]) -> str:
        """Extracts a raw string value, handling wrappers."""
        if isinstance(node, str):
            return node
            
        if "value" in node:
            return node["value"]
            
        # Fallback for Entity wrappers used as values
        if node.get("function") == CONSTRUCTOR_ENTITY:
             if len(node.get("args", [])) > 1:
                 return node["args"][1].lower()
             
        return str(node)

    # --- Helper: Safe Fact Retrieval (Fix for Missing Method) ---
    def _get_lexicon_facts(self, lang: str, qid: Optional[str], prop: str) -> List[str]:
        """
        Safely retrieves facts/claims from a lexicon entry.
        Handles the case where lexicon.get_facts() doesn't exist yet.
        """
        # [FIX] Local import to avoid circular dependency
        from app.shared.lexicon import lexicon

        if not qid: 
            return []
        
        # Try finding the entry first
        try:
            entry = lexicon.get_entry(lang, qid)
            if not entry:
                return []
                
            # If entry is a dict (JSON shard)
            if isinstance(entry, dict):
                # FIX: LexiconRuntime merges facts into root features, check there too
                return entry.get("facts", {}).get(prop, []) or entry.get("features", {}).get(prop, [])
                
            # If entry is an Object (LexiconEntry dataclass)
            # Note: The v2.1 LexiconEntry dataclass might NOT have a 'facts' field yet.
            # We check for it safely.
            if hasattr(entry, "facts") and isinstance(entry.facts, dict):
                return entry.facts.get(prop, [])
            
            # FIX: In app.shared.lexicon, facts are merged into `features`.
            if hasattr(entry, "features") and isinstance(entry.features, dict):
                 return entry.features.get(prop, [])
                 
            return []
        except Exception as e:
            logger.warning(f"Failed to retrieve facts for {qid}: {e}")
            return []

# Global Singleton
ninai_adapter = NinaiAdapter()