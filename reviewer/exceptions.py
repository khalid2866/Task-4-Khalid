"""Typed exceptions for the code reviewer pipeline.

Each pipeline phase raises its own error family so the CLI can exit
with a precise, human-readable explanation instead of a traceback.
"""


class ReviewerError(Exception):
    """Base class for every reviewer-pipeline failure."""


# ---------------------------------------------------------------------------
# Phase 1 — ingestion triage
# ---------------------------------------------------------------------------
class IngestionError(ReviewerError):
    """The raw file could not be ingested into the string buffer."""


class FileMissingError(IngestionError):
    """The specified path does not point to a valid file."""


class AccessDeniedError(IngestionError):
    """The file has restricted read permissions."""


class EncodingValidationError(IngestionError):
    """The file could not be decoded with any robust codec."""


# ---------------------------------------------------------------------------
# Phase 2 — orchestration / API client
# ---------------------------------------------------------------------------
class OrchestrationError(ReviewerError):
    """The payload could not be assembled for the review engine."""


class EngineError(ReviewerError):
    """The review engine failed to produce a response."""


# ---------------------------------------------------------------------------
# Phase 3 — structured output validation
# ---------------------------------------------------------------------------
class ValidationError(ReviewerError):
    """The engine response failed structured-output validation and was
    rejected so a malformed report never reaches the pipeline."""
