from __future__ import annotations

import os
import contextlib
import requests
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from ..infrastructure.logging import get_logger
from ..infrastructure.ollama.client import OllamaEmbeddingService
from ..infrastructure.qdrant.client import QdrantVectorStore
from ..infrastructure.timeouts import http_timeout_seconds, operation_timeout
from ..infrastructure.config import qdrant_url
from ..ingestion.memory_bank_loader import load_memory_items
from ..application.dto import EnsureCollectionRequest, UpsertMemoryRequest, QueryRequest
from ..application.use_cases.ensure_collection import EnsureCollectionUseCase
from ..application.use_cases.upsert_memory import UpsertMemoryUseCase
from ..application.use_cases.query_memory import QueryMemoryUseCase

logger = get_logger("vector_memory.mcp.api")


def _parse_dotenv(dotenv_path: Path) -> Dict[str, str]:
    """Parse a simple .env file (KEY=VALUE per line, '#' comments)."""
    env: Dict[str, str] = {}
    if dotenv_path.exists():
        with contextlib.suppress(Exception):
            for raw in dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = raw.strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k:
                    env[k] = v
    return env


def _env_get(key: str) -> Optional[str]:
    """Get environment value from process env, falling back to .env in CWD."""
    v = os.getenv(key)
    if v is not None and v.strip():
        return v.strip()
    local = _parse_dotenv(Path(".env"))
    v2 = local.get(key)
    return v2.strip() if v2 is not None and v2.strip() else None


def _list_additional_collections() -> list[str]:
    """List configured additional collections from env/.env (MEMORY_COLLECTION_NAME_2+)."""
    out: list[str] = []
    merged: Dict[str, str] = {}
    merged.update(_parse_dotenv(Path(".env")))
    for k, v in os.environ.items():
        if isinstance(k, str) and isinstance(v, str):
            merged[k] = v
    out.extend(
        v.strip()
        for k, v in merged.items()
        if k.startswith("MEMORY_COLLECTION_NAME_")
        and isinstance(v, str)
        and v.strip()
    )
    # de-duplicate preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def _allowed_collections() -> list[str]:
    """Allowed collection names declared in env/.env: primary + MEMORY_COLLECTION_NAME_2..N."""
    allowed: list[str] = []
    primary = _env_get("MEMORY_COLLECTION_NAME")
    if primary and primary not in allowed:
        allowed.append(primary)
    for n in _list_additional_collections():
        if n and n not in allowed:
            allowed.append(n)
    return allowed


def _list_qdrant_collections() -> list[str]:
    """Fetch current Qdrant collections for helpful error messages."""
    try:
        timeout = http_timeout_seconds()
        base = qdrant_url()
        with operation_timeout(timeout):
            return list_collections(base, timeout)
    except Exception:
        return []

def list_collections(base, timeout):
    """
    Helper function to fetch and list all Qdrant collection names.

    This function sends a GET request to the Qdrant collections endpoint and extracts
    the names of all available collections, returning them as a sorted list.

    Args:
        base: The base URL for the Qdrant service.
        timeout: The timeout value for the HTTP request.

    Returns:
        list[str]: A sorted list of collection names.
    """
    r = requests.get(f"{base}/collections", timeout=timeout)
    r.raise_for_status()
    data = r.json() or {}
    cols: list[str] = []
    for it in (data.get("result", {}).get("collections") or []):
        name = it.get("name")
        if isinstance(name, str) and name.strip():
            cols.append(name.strip())
    return sorted(set(cols))


def vector_create_collection(collection: str, dim: Optional[int] = None, distance: str = "Cosine", recreate: bool = False) -> Dict[str, Any]:
    """Create/ensure a collection, gated by env allowlist (primary + *_2..N)."""
    emb = OllamaEmbeddingService()
    store = QdrantVectorStore()
    allowed = _allowed_collections()
    if collection not in allowed:
        return {
            "status": "error",
            "error": f"Collection '{collection}' is not declared in environment (.env). "
                     f"Add it as MEMORY_COLLECTION_NAME or MEMORY_COLLECTION_NAME_2..N before creation.",
            "requested": collection,
            "allowed_env_collections": allowed,
            "available_collections": _list_qdrant_collections(),
        }
    EnsureCollectionUseCase(emb, store).execute(
        EnsureCollectionRequest(collection=collection, dim=dim, distance=distance, recreate=recreate)
    )
    return {"status": "ok", "collection": collection, "dimension": int(dim or emb.get_dimension()), "distance": distance}


def vector_index_memory_bank(collection: str, directory: str = "memory-bank", id_namespace: str = "mem", max_items: Optional[int] = None) -> Dict[str, Any]:
    emb = OllamaEmbeddingService()
    store = QdrantVectorStore()
    root = Path(directory)
    items = load_memory_items(root)
    if max_items:
        items = items[: int(max_items)]
    logger.info("MCP index | collection=%s | dir=%s | candidates=%d", collection, root, len(items))
    resp = UpsertMemoryUseCase(emb, store).execute(
        UpsertMemoryRequest(collection=collection, items=items, id_namespace=id_namespace)
    )
    return resp.raw  # provider JSON


def vector_query(collection: str, q: str, k: int = 5, with_payload: bool = True, score_threshold: Optional[float] = None) -> Dict[str, Any]:
    """Query a collection; if the collection does not exist, return an error listing available names."""
    emb = OllamaEmbeddingService()
    store = QdrantVectorStore()
    available = _list_qdrant_collections()
    if collection not in available:
        return {
            "status": "error",
            "error": f"Collection '{collection}' does not exist in Qdrant.",
            "requested": collection,
            "available_collections": available,
        }
    results = QueryMemoryUseCase(emb, store).execute(
        QueryRequest(
            collection=collection,
            query=q,
            k=k,
            with_payload=with_payload,
            score_threshold=score_threshold,
        )
    )
    return {"status": "ok", "collection": collection, "result": [r.__dict__ for r in results]}


def vector_delete(collection: str, ids: Sequence[str]) -> Dict[str, Any]:
    """Simple delete by IDs using Qdrant REST; scoped to MCP surface only."""
    import requests
    from ..infrastructure.timeouts import http_timeout_seconds, operation_timeout
    from ..infrastructure.config import qdrant_url

    timeout = http_timeout_seconds()
    base = qdrant_url()
    url = f"{base}/collections/{collection}/points/delete?wait=true"
    body = {"points": list(ids)}
    with operation_timeout(timeout):
        r = requests.post(url, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
