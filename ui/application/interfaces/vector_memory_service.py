"""
Vector Memory Service Interface.

Defines contract for vector memory operations.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict


class IVectorMemoryService(ABC):
    """Interface for vector memory query operations."""

    @abstractmethod
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
        ...

    @abstractmethod
    def create_collection(self, name: str) -> None:
        """Create or ensure a collection exists in the backing store.

        Parameters:
            name: The collection name to create.

        Behavior:
            Implementations may create the collection explicitly or ensure it
            exists with default parameters (dimension from embedding service and
            cosine distance). If the backend creates collections implicitly,
            implementations may no-op but should not raise.

        Raises:
            Exception: When an explicit create/ensure operation fails.
        """
        ...

    @abstractmethod
    def insert_data(self, collection: str, text: str, metadata: Optional[Dict[str, Any]] = None, id_namespace: str = "ui") -> None:
        """Insert a single text item into a collection.

        Parameters:
            collection: Target collection name.
            text: Text content to embed and store.
            metadata: Optional arbitrary metadata dictionary to persist with the item.
            id_namespace: Logical namespace for deterministic IDs (default ``"ui"``).

        Behavior:
            Implementations should embed the text, construct a deterministic point ID,
            and upsert into the vector store. If the collection does not exist, they may
            choose to ensure it exists first or raise an error.

        Raises:
            Exception: If the operation fails (embedding, connectivity, or store errors).
        """
        ...

    @abstractmethod
    def insert_many(self, collection: str, items: List[Dict[str, Any]], id_namespace: str = "ui") -> None:
        """Insert multiple text items into a collection in a single upsert.

        Parameters:
            collection: Target collection name.
            items: A list of dictionaries with shape {"text": str, "meta": Dict[str, Any]}.
            id_namespace: Logical namespace for deterministic IDs (default ``"ui"``).

        Raises:
            Exception: If the operation fails.
        """
        ...

    @abstractmethod
    def list_collections(self) -> List[Dict[str, Any]]:
        """List available collections with basic metadata.

        Returns:
            A list of dictionaries each containing at least:
              - ``name``: The collection name (str)
              - ``dim``: Embedding dimension if known (int) or ``None`` when unavailable

        Notes:
            Implementations should handle backends that do not expose dimensions
            by returning ``None`` for the ``dim`` field.
        """
        ...
