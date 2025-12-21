import json
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import ValidationError

from app.core.domain.frame import BioFrame, EventFrame, RelationalFrame
from app.shared.config import settings

# Logger setup
logger = logging.getLogger(settings.OTEL_SERVICE_NAME)

# --- CONSTANTS: The Ninai Protocol Ledger ---
# Matches keys defined in Ninai/constructors.py and docs/14-VAR_FIX_LEDGER.md
CONSTRUCTOR_STATEMENT = "ninai.constructors.Statement"
CONSTRUCTOR_ENTITY = "ninai.constructors.Entity"
CONSTRUCTOR_LIST = "ninai.constructors.List"
TYPE_BIO = "ninai.types.Bio"
TYPE_EVENT = "ninai.types.Event"

class NinaiAdapter:
    """
    The Bridge between the external Ninai Protocol (Recursive JSON Objects)
    and the internal Abstract Wiki Architect Domain (Flat Pydantic Frames).
    """

    def parse(self, ninai_payload: Dict[str, Any]) -> Union[BioFrame, EventFrame, RelationalFrame]:
        """
        Main entry point. Recursively parses the input JSON tree.
        
        Args:
            ninai_payload: The raw JSON dictionary received from the API/Wire.
            
        Returns:
            A validated internal Pydantic Frame (BioFrame, etc.).
            
        Raises:
            ValueError: If the structure is invalid or the intent is unknown.
        """
        # 1. Validate Root Structure
        func = ninai_payload.get("function")
        if func != CONSTRUCTOR_STATEMENT:
            raise ValueError(f"Invalid Root: Expected '{CONSTRUCTOR_STATEMENT}', got '{func}'")

        args = ninai_payload.get("args", [])
        if not args:
            raise ValueError("Invalid Statement: 'args' list is empty.")

        # 2. Extract Intent (The first argument is usually the Type definition)
        intent_obj = args[0]
        intent_type = intent_obj.get("type")

        # 3. Route to specific handler
        if intent_type == TYPE_BIO:
            return self._parse_bio(args)
        elif intent_type == TYPE_EVENT:
            return self._parse_event(args)
        else:
            raise ValueError(f"Unsupported Ninai Type: {intent_type}")

    def _parse_bio(self, args: List[Dict[str, Any]]) -> BioFrame:
        """
        Parses a Biographical Statement.
        Expected Ninai Args: [Type, Subject(Entity), Profession(Entity), Nationality(Entity)?]
        """
        try:
            # Subject (Arg 1)
            subject_node = args[1]
            subject_name = self._extract_label(subject_node)
            subject_qid = self._extract_qid(subject_node)
            
            # Profession (Arg 2)
            prof_node = args[2]
            profession_key = self._extract_value(prof_node) # e.g., "physicist"

            # Optional Nationality (Arg 3)
            nationality_key = None
            if len(args) > 3:
                nat_node = args[3]
                nationality_key = self._extract_value(nat_node)

            return BioFrame(
                name=subject_name,
                qid=subject_qid,
                profession=profession_key,
                nationality=nationality_key,
                # Gender is inferred from QID lookup in Lexicon, or passed explicitly in metadata
                gender=None 
            )
        except IndexError:
            raise ValueError("Malformed BioFrame: Missing required arguments.")
        except ValidationError as e:
            raise ValueError(f"Validation Error in BioFrame: {e}")

    def _parse_event(self, args: List[Dict[str, Any]]) -> EventFrame:
        """
        Parses an Event Statement.
        """
        # Implementation placeholder matching the pattern above
        # For v2.0 MVP, we focus on BioFrame correctness first.
        raise NotImplementedError("Event parsing is in roadmap for v2.1")

    # --- Helper: Recursive Tree Walkers ---

    def _extract_label(self, node: Dict[str, Any]) -> str:
        """
        Extracts the human-readable label from an Entity node.
        """
        if node.get("function") == CONSTRUCTOR_ENTITY:
            # { "function": "Entity", "args": ["Q42", "Douglas Adams"] }
            return node["args"][1]
        return "Unknown"

    def _extract_qid(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Extracts the Wikidata ID (QID) from an Entity node.
        """
        if node.get("function") == CONSTRUCTOR_ENTITY:
            return node["args"][0]
        return None

    def _extract_value(self, node: Dict[str, Any]) -> str:
        """
        Extracts a raw string value, handling direct strings or wrapped entities.
        """
        # If it's a simple string literal
        if isinstance(node, str):
            return node
            
        # If it's a wrapper object
        if "value" in node:
            return node["value"]
            
        # Fallback for Entity wrappers used as values
        if node.get("function") == CONSTRUCTOR_ENTITY:
             # Return the label (Arg 1) as the key
             return node["args"][1].lower()
             
        return str(node)

# Global Singleton
ninai_adapter = NinaiAdapter()