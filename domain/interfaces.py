from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import Vector, Point, QueryResult


class EmbeddingService(ABC):
    """Port for embedding provider (e.g., Ollama)."""

    @abstractmethod
    def embed_texts(self, texts: List[str]) -> List[Vector]:
        """Embed a batch of texts into vectors.

        Raises:
            Exception: Provider/network failures should surface; use-case decides.
        """
        raise NotImplementedError

    @abstractmethod
    def get_dimension(self) -> int:
        """Return embedding dimension, probing provider if needed."""
        raise NotImplementedError


class VectorStore(ABC):
    """Port for vector storage (e.g., Qdrant)."""

    @abstractmethod
    def ensure_collection(self, name: str, dim: int, distance: str = "Cosine", recreate: bool = False) -> None:
        """Ensure collection exists with expected dimension."""
        raise NotImplementedError

    @abstractmethod
    def upsert_points(self, name: str, points: List[Point]) -> dict:
        """Upsert list of points; returns provider response JSON."""
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        name: str,
        vector: Vector,
        limit: int = 5,
        with_payload: bool = True,
        score_threshold: Optional[float] = None,
    ) -> List[QueryResult]:
        """Search similar points; returns list of QueryResult."""
        raise NotImplementedError
