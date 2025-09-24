from __future__ import annotations

from typing import List
import requests

from ...domain.interfaces import EmbeddingService
from ...domain.models import Vector
from ..timeouts import http_timeout_seconds, operation_timeout
from ..config import ollama_url, embed_model


class OllamaEmbeddingService(EmbeddingService):
    """Embedding adapter for Ollama /api/embeddings."""

    def embed_texts(self, texts: List[str]) -> List[Vector]:
        if not texts:
            return []
        base = ollama_url()
        url = f"{base}/api/embeddings"
        timeout = http_timeout_seconds()
        model = embed_model()
        out: List[Vector] = []
        with operation_timeout(timeout):
            for t in texts:
                r = requests.post(url, json={"model": model, "prompt": t}, timeout=timeout)
                r.raise_for_status()
                data = r.json()
                values = [float(x) for x in data["embedding"]]
                out.append(Vector(values=values, dim=len(values)))
        return out

    def get_dimension(self) -> int:
        vecs = self.embed_texts(["probe"])
        if not vecs:
            raise RuntimeError("Embedding dimension probe failed (no vectors)")
        return vecs[0].dim
