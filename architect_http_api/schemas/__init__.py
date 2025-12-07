"""
Top-level export module for HTTP API schemas.
"""
# Import submodules
from . import common
from . import generic
from . import ai
from . import generations
from . import entities
from . import frames_metadata

# Common primitives
from .common import (
    ErrorResponse,
    Pagination,
)

# AI / intent
from .ai import (
    IntentKind,
    IntentInput,
    IntentResult,
    AICommandRequest,
    AICommandResponse,
    AIFramePatch,
    AIMessage,
)

# Generations
from .generations import (
    GenerationRequest,
    GenerationResponse,
    GenerationStatus,
    GenerationResult,
    GenerationOptions,
)

# Domain entities
from .entities import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntityListItem,
    EntityListResponse,
    EntityDeleteResponse,
    # Helper alias we will add to entities.py
    EntityRead, 
)

# Frames / metadata
from .frames_metadata import (
    FrameFieldMetadata,
    FrameTypeMetadata,
    FrameFamilyMetadata,
    FramesCatalogue,
    # Helper alias we will add to frames_metadata.py
    FrameMetadata,
)

# Backward Compatibility Aliases 
# (Maps old names to new structures to prevent other import errors)
FrameSummary = EntityListItem
WikiEntity = Entity

__all__ = [
    # Submodules
    "common", "generic", "ai", "generations", "entities", "frames_metadata",
    
    # Common
    "ErrorResponse", "Pagination",
    
    # AI
    "IntentKind", "IntentInput", "IntentResult", 
    "AICommandRequest", "AICommandResponse", "AIFramePatch", "AIMessage",
    
    # Generation
    "GenerationRequest", "GenerationResponse", "GenerationStatus", 
    "GenerationResult", "GenerationOptions",
    
    # Entities
    "Entity", "EntityCreate", "EntityUpdate", "EntityListItem", 
    "EntityListResponse", "EntityDeleteResponse", "EntityRead",
    "FrameSummary", "WikiEntity",
    
    # Frames
    "FrameFieldMetadata", "FrameTypeMetadata", "FrameFamilyMetadata", 
    "FramesCatalogue", "FrameMetadata",
]