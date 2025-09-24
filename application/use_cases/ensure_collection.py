from __future__ import annotations

from ..dto import EnsureCollectionRequest
from ...domain.interfaces import EmbeddingService, VectorStore


class EnsureCollectionUseCase:
    """Use-case: ensure the collection exists with the expected dimension."""

    def __init__(self, embeddings: EmbeddingService, store: VectorStore) -> None:
        self._emb = embeddings
        self._store = store

    def execute(self, req: EnsureCollectionRequest) -> None:
        """
        Ensures that the specified collection exists with the correct dimension and distance metric.

        Uses the provided dimension or probes the embedding service for the default dimension, then creates or updates the collection as needed.

        Args:
            req: The request object containing collection name, dimension, distance, and recreate flag.

        Returns:
            None
        """
        dim = int(req.dim or self._emb.get_dimension())
        self._store.ensure_collection(req.collection, dim, req.distance, req.recreate)
