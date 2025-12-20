# app/core/domain/exceptions.py
class DomainError(Exception):
    """Base class for all domain-level exceptions."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

# --- Entity Not Found Errors ---

class LanguageNotFoundError(DomainError):
    """Raised when an operation is requested for a language code that is not supported."""
    def __init__(self, lang_code: str):
        super().__init__(f"Language '{lang_code}' is not supported or not found in the registry.")

class LexiconEntryNotFoundError(DomainError):
    """Raised when a specific lemma or QID is missing from the lexicon."""
    def __init__(self, identifier: str, lang_code: str):
        super().__init__(f"Lexicon entry '{identifier}' not found for language '{lang_code}'.")

# --- Validation Errors ---

class InvalidFrameError(DomainError):
    """Raised when a semantic frame fails validation logic (e.g., missing required fields)."""
    def __init__(self, reason: str):
        super().__init__(f"Invalid Semantic Frame: {reason}")

class UnsupportedFrameTypeError(DomainError):
    """Raised when the engine does not know how to process a specific frame type."""
    def __init__(self, frame_type: str):
        super().__init__(f"Frame type '{frame_type}' is not supported by the current engine.")

# --- Process/State Errors ---

class LanguageBuildInProgressError(DomainError):
    """Raised when attempting to build a language that is already building."""
    def __init__(self, lang_code: str):
        super().__init__(f"Build for language '{lang_code}' is already in progress.")

class GrammarCompilationError(DomainError):
    """Raised when the underlying grammar engine (GF) fails to compile."""
    def __init__(self, lang_code: str, details: str):
        super().__init__(f"Grammar compilation failed for '{lang_code}': {details}")