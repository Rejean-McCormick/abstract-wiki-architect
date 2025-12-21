from typing import Optional, Literal
from pydantic import BaseModel, Field
import uuid

class DiscourseEntity(BaseModel):
    """
    Represents an entity mentioned in the discourse history.
    Used to track gender and recency for pronominalization.
    
    Fields:
      - label: The surface text (e.g., "Marie Curie")
      - gender: Grammatical gender for pronoun selection.
      - qid: Wikidata ID (e.g., "Q7186").
      - recency: How many turns ago it was mentioned (0 = current).
    """
    label: str
    gender: Literal["m", "f", "n", "c"]  # m=masc, f=fem, n=neut, c=common
    qid: str = Field(..., pattern=r"^Q\d+$") 
    recency: int = 0

class SessionContext(BaseModel):
    """
    The state of a conversation session, serializable to Redis.
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    history_depth: int = 0
    current_focus: Optional[DiscourseEntity] = None  # The Backward-Looking Center (Cb)

    def should_pronominalize(self, new_qid: str) -> bool:
        """
        Decides if the new subject should be replaced by a pronoun.
        
        Logic (Centering Theory):
        If the new subject matches the entity currently in focus (Cb) from 
        the previous utterance, we can safely pronominalize.
        """
        if not self.current_focus:
            return False
        return self.current_focus.qid == new_qid

    def update_focus(self, entity: DiscourseEntity) -> None:
        """
        Updates the session state after a successful generation.
        Sets the new entity as the Backward-Looking Center for the next turn.
        """
        self.current_focus = entity
        self.history_depth += 1