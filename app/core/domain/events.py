# app/core/domain/events.py
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

class EventType(str, Enum):
    """
    Registry of all system events.
    Using an Enum ensures type safety across the distributed system.
    """
    # Lifecycle Events
    BUILD_REQUESTED = "language.build.requested"
    BUILD_STARTED = "language.build.started"
    BUILD_COMPLETED = "language.build.completed"
    BUILD_FAILED = "language.build.failed"
    
    # Data Events
    LEXICON_UPDATED = "lexicon.updated"
    LEXICON_FETCH_REQUIRED = "lexicon.fetch.required"
    
    # System Events
    HEALTH_CHECK = "system.health_check"

class SystemEvent(BaseModel):
    """
    The standard envelope for all messages in the Event Bus.
    
    Attributes:
        id: Unique UUID for idempotency checks.
        type: The classification of the event.
        payload: The actual data (e.g., {'lang_code': 'fr'}).
        trace_id: OpenTelemetry Trace ID for distributed debugging.
        timestamp: When the event occurred (UTC).
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    payload: Dict[str, Any]
    trace_id: Optional[str] = None
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())

    # Pydantic V2 Configuration
    model_config = ConfigDict(use_enum_values=True)

# --- Specific Payloads (Optional but recommended for strict typing) ---

class BuildRequestedPayload(BaseModel):
    lang_code: str
    strategy: str = "fast"  # 'fast' (Pidgin) or 'full' (Grammar)
    requester_id: Optional[str] = None

class BuildFailedPayload(BaseModel):
    lang_code: str
    error_code: str
    details: str