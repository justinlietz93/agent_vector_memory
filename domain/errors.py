from __future__ import annotations


class EmbeddingError(RuntimeError):
    """Raised when embedding provider fails."""


class VectorStoreError(RuntimeError):
    """Raised when vector store provider fails."""


class ContractError(ValueError):
    """Raised when request violates documented contract (e.g., ID format)."""
