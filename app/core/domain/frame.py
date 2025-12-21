from typing import Optional, Literal
from pydantic import BaseModel, Field

class BaseFrame(BaseModel):
    """
    Abstract base class for all Semantic Frames.
    Contains metadata fields used across all intent types.
    """
    context_id: Optional[str] = Field(
        default=None, 
        description="UUID linking this frame to a Discourse Session (Redis)."
    )
    style: Literal["simple", "formal"] = "simple"

class BioFrame(BaseFrame):
    """
    Represents an introductory biographical sentence.
    Example: "Marie Curie is a Polish physicist."
    """
    frame_type: Literal["bio"] = "bio"
    
    name: str = Field(..., description="The subject's proper name (Surface Form).")
    
    # Lexicon Lookup Keys
    profession: str = Field(..., description="Key in people.json (e.g., 'physicist').")
    nationality: Optional[str] = Field(default=None, description="Key in geography.json (e.g., 'polish').")
    
    # Morphology Overrides
    gender: Optional[Literal["m", "f", "n"]] = Field(
        default=None, 
        description="Grammatical gender override for the subject."
    )
    
    # Ninai/Wikidata Metadata
    qid: Optional[str] = Field(
        default=None, 
        description="Wikidata ID (e.g., 'Q7186') for entity grounding."
    )

class EventFrame(BaseFrame):
    """
    Represents a temporal event.
    Example: "She was born in 1867."
    """
    frame_type: Literal["event"] = "event"
    
    event_type: Literal["birth", "death", "award", "discovery"]
    subject: str
    
    date: Optional[str] = Field(default=None, description="Year or ISO date string.")
    location: Optional[str] = Field(default=None, description="Key in geography.json.")

class RelationalFrame(BaseFrame):
    """
    Represents a direct relationship between two entities.
    Example: "Pierre Curie was the spouse of Marie Curie."
    """
    frame_type: Literal["relational"] = "relational"
    
    subject: str
    relation: str = Field(..., description="Predicate key (e.g., 'spouse_of').")
    object: str