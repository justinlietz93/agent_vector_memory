from __future__ import annotations

import uuid
from typing import List, Dict

from ..dto import UpsertMemoryRequest, UpsertResponse
from ...domain.interfaces import EmbeddingService, VectorStore
from ...domain.models import Vector, MemoryItem, Point
from ...infrastructure.config import payload_text_max


def _make_uuid(namespace: str, source: str, text: str) -> str:
    ns = f"{namespace}|{source}|{text}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, ns))


class UpsertMemoryUseCase:
    """Use-case: embed items, build points with deterministic UUIDv5 IDs, and upsert into the store."""

    def __init__(self, embeddings: EmbeddingService, store: VectorStore) -> None:
        self._emb = embeddings
        self._store = store

    def execute(self, req: UpsertMemoryRequest) -> UpsertResponse:
        items = req.items or []
        texts = [it.text for it in items]
        vecs = self._emb.embed_texts(texts)
        if not vecs:
            return UpsertResponse(provider="qdrant", raw={"status": "ok", "result": {"operation_id": None, "points": 0}})
        dim = vecs[0].dim
        for v in vecs:
            if v.dim != dim:
                raise ValueError(f"Inconsistent embedding dimension: got {v.dim}, expected {dim}")

        max_chars = payload_text_max()
        points: List[Point] = []
        for it, v in zip(items, vecs):
            source = str(it.meta.get("source", ""))
            pid = _make_uuid(req.id_namespace, source, it.text)
            payload: Dict[str, object] = {
                "text_preview": it.text[:max_chars],
                "text_len": len(it.text),
                "meta": it.meta,
            }
            points.append(Point(id=pid, vector=Vector(values=v.values, dim=v.dim), payload=payload))

        raw = self._store.upsert_points(req.collection, points)
        return UpsertResponse(provider="qdrant", raw=raw)
