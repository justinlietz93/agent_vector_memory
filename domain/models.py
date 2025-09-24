from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MemoryItem:
    """A single memory-bank document to be indexed.

    Fields:
        text: Raw content to embed (full text; callers may trim into payload).
        meta: Arbitrary metadata (e.g., source path, filename, mtime).
    """
    text: str
    meta: Dict[str, object]


@dataclass(frozen=True)
class Vector:
    """Embedding vector with explicit dimension.

    Fields:
        values: The numeric embedding.
        dim: Dimension; validated by application/use-cases.
    """
    values: List[float]
    dim: int


@dataclass(frozen=True)
class Point:
    """A point to upsert into the vector store.

    Fields:
        id: Qdrant-valid ID (UUID or uint64).
        vector: Embedding vector (default unnamed vector).
        payload: Arbitrary payload (should contain text_preview, text_len, meta).
    """
    id: str
    vector: Vector
    payload: Dict[str, object]


@dataclass(frozen=True)
class QueryResult:
    """Vector search match returned by the store.

    Fields:
        id: Point ID.
        score: Similarity score (store-defined; higher is better for cosine).
        payload: Returned payload.
    """
    id: str
    score: float
    payload: Dict[str, object]
