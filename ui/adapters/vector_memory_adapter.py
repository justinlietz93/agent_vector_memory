"""
Vector Memory Adapter.

Infrastructure implementation of IVectorMemoryService.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Any, Optional, Dict

from ..application.interfaces.vector_memory_service import IVectorMemoryService


class VectorMemoryAdapter(IVectorMemoryService):
    """Adapter for vector memory operations using the vector_memory module."""

    def __init__(self):
        """Initialize adapter with proper imports."""
        self._setup_imports()

    def _setup_imports(self) -> None:
        """Setup imports to vector memory components."""
        try:
            # Add root directory to path for imports
            root_dir = Path(__file__).parent.parent.parent.parent
            if str(root_dir) not in sys.path:
                sys.path.insert(0, str(root_dir))

            # Import vector memory components
            from vector_memory.application.dto import QueryRequest, EnsureCollectionRequest, UpsertMemoryRequest
            from vector_memory.application.use_cases.query_memory import QueryMemoryUseCase
            from vector_memory.application.use_cases.ensure_collection import EnsureCollectionUseCase
            from vector_memory.application.use_cases.upsert_memory import UpsertMemoryUseCase
            from vector_memory.infrastructure.ollama.client import OllamaEmbeddingService
            from vector_memory.infrastructure.qdrant.client import QdrantVectorStore
            from vector_memory.domain.models import MemoryItem

            self._QueryRequest = QueryRequest
            self._EnsureCollectionRequest = EnsureCollectionRequest
            self._UpsertMemoryRequest = UpsertMemoryRequest
            self._QueryMemoryUseCase = QueryMemoryUseCase
            self._EnsureCollectionUseCase = EnsureCollectionUseCase
            self._UpsertMemoryUseCase = UpsertMemoryUseCase
            self._OllamaEmbeddingService = OllamaEmbeddingService
            self._QdrantVectorStore = QdrantVectorStore
            self._MemoryItem = MemoryItem

        except ImportError as e:
            raise ImportError(f"Failed to import vector memory components: {e}")

    def query_memory(self, collection: str, prompt: str, k: int) -> List[Any]:
        """
        Query vector memory for relevant results.

        Args:
            collection: Collection name to query
            prompt: Query text
            k: Number of results to return

        Returns:
            List of search results with scores and metadata

        Raises:
            VectorMemoryError: If query fails
        """
        try:
            # Build dependencies
            emb = self._OllamaEmbeddingService()
            store = self._QdrantVectorStore()
            use_case = self._QueryMemoryUseCase(embeddings=emb, store=store)

            # Execute query
            request = self._QueryRequest(
                collection=collection,
                query=prompt,
                k=k,
                with_payload=True
            )

            results = use_case.execute(request)
            return results or []

        except Exception as e:
            raise Exception(f"Vector memory query failed: {e}") from e

    def create_collection(self, name: str) -> None:
        """Ensure a collection exists using default embedding dimension and cosine distance."""
        try:
            emb = self._OllamaEmbeddingService()
            store = self._QdrantVectorStore()
            use_case = self._EnsureCollectionUseCase(embeddings=emb, store=store)
            req = self._EnsureCollectionRequest(collection=name, dim=None, distance="Cosine", recreate=False)
            use_case.execute(req)
        except Exception as e:
            raise Exception(f"Create collection failed: {e}") from e

    def insert_data(self, collection: str, text: str, metadata: Optional[Dict[str, Any]] = None, id_namespace: str = "ui") -> None:
        """Insert a single text item into the vector store for the given collection."""
        try:
            emb = self._OllamaEmbeddingService()
            store = self._QdrantVectorStore()

            # Optionally ensure collection exists (safe idempotent op)
            ensure = self._EnsureCollectionUseCase(embeddings=emb, store=store)
            ensure.execute(self._EnsureCollectionRequest(collection=collection, dim=None, distance="Cosine", recreate=False))

            meta = metadata or {}
            item = self._MemoryItem(text=text, meta=meta)
            req = self._UpsertMemoryRequest(collection=collection, items=[item], id_namespace=id_namespace)
            self._UpsertMemoryUseCase(embeddings=emb, store=store).execute(req)
        except Exception as e:
            raise Exception(f"Insert data failed: {e}") from e

    def insert_many(self, collection: str, items: List[Dict[str, Any]], id_namespace: str = "ui") -> None:
        """Insert multiple text items into the vector store for the given collection."""
        try:
            emb = self._OllamaEmbeddingService()
            store = self._QdrantVectorStore()

            ensure = self._EnsureCollectionUseCase(embeddings=emb, store=store)
            ensure.execute(self._EnsureCollectionRequest(collection=collection, dim=None, distance="Cosine", recreate=False))

            mem_items = [self._MemoryItem(text=str(it.get("text", "")), meta=dict(it.get("meta", {}))) for it in items if str(it.get("text", "")).strip()]
            if not mem_items:
                return
            req = self._UpsertMemoryRequest(collection=collection, items=mem_items, id_namespace=id_namespace)
            self._UpsertMemoryUseCase(embeddings=emb, store=store).execute(req)
        except Exception as e:
            raise Exception(f"Insert many failed: {e}") from e

    def list_collections(self) -> List[Dict[str, Any]]:
        """Return available collections with their dimensions when available.

        Uses the underlying Qdrant client to list collections and fetch
        per-collection configuration for dimensions. If a backend error occurs,
        an empty list is returned to avoid breaking the UI.
        """
        try:
            store = self._QdrantVectorStore()
            if hasattr(store, "list_collections_info"):
                return list(getattr(store, "list_collections_info")() or [])
            # Fallback: if helper is missing, attempt minimal behavior
            names = []
            if hasattr(store, "list_collections"):
                names = list(getattr(store, "list_collections")() or [])
            return [{"name": n, "dim": None} for n in names]
        except Exception:
            return []
