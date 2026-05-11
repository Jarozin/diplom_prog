class ModelError(Exception):
    """Base error for decision models."""

class StructureError(ModelError):
    """Invalid model structure (missing blocks, zero columns, etc.)."""

class NormalizationError(ModelError):
    """Raised when labeled normalization of vectors/matrices fails (label mismatch, etc.)."""

class ConsistencyError(ModelError):
    """Consistency threshold violations."""

