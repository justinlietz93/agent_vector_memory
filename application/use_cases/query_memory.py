from __future__ import annotations

from ..dto import QueryRequest
from ...domain.interfaces import EmbeddingService, VectorStore
from ...domain.models import Vector


class QueryMemoryUseCase:
    """Use-case: embed query string and search the store."""

    def __init__(self, embeddings: EmbeddingService, store: VectorStore) -> None:
        self._emb = embeddings
        self._store = store

    def execute(self, req: QueryRequest):
        vec = self._emb.embed_texts([req.query])[0]
        return self._store.search(
            name=req.collection,
            vector=Vector(values=vec.values, dim=vec.dim),
            limit=req.k,
            with_payload=req.with_payload,
            score_threshold=req.score_threshold,
        )
