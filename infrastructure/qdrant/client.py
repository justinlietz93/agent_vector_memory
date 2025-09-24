from __future__ import annotations

from typing import List, Optional
import os
from pathlib import Path
import requests

from ...domain.interfaces import VectorStore
from ...domain.models import Vector, Point, QueryResult
from ..timeouts import http_timeout_seconds, operation_timeout
from ..config import qdrant_url
from contextlib import suppress


def _parse_shell_kv_file(path: Path) -> dict:
    """
    Minimal KEY=VALUE parser for the watcher lock file.
    Ignores comments and blank lines; strips single/double quotes around values.
    """
    data: dict = {}
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = raw.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                data[k] = v
    except Exception:
        return {}
    return data


def _load_thread_id_from_lock() -> Optional[str]:
    """
    Read THREAD_ID from the pinned conversation lock file if thread filtering is enabled.

    Controls (env):
    - VM_THREAD_FILTER: "1"/"true"/"yes" to enable (default). "0"/"false"/"no" to disable.
    - VM_THREAD_LOCK_FILE or LOCK_FILE: explicit path to the lock file.
      Default resolves to vector_memory/tools/current_thread.lock relative to this module.
    """
    enabled = str(os.getenv("VM_THREAD_FILTER", "1")).lower() in {"1", "true", "yes"}
    if not enabled:
        return None

    lock_env = os.getenv("VM_THREAD_LOCK_FILE") or os.getenv("LOCK_FILE")
    if lock_env:
        p = Path(lock_env).expanduser()
    else:
        here = Path(__file__).resolve()
        # .../vector_memory/infrastructure/qdrant/client.py -> vector_memory
        vm_root = here.parent.parent.parent
        p = vm_root / "tools" / "current_thread.lock"

    if not p.exists():
        return None

    kv = _parse_shell_kv_file(p)
    tid = kv.get("THREAD_ID")
    return tid.strip() if isinstance(tid, str) and tid.strip() else None


def current_thread_id() -> Optional[str]:
    """Return the active thread identifier when the filter is enabled."""

    return _load_thread_id_from_lock()


class QdrantVectorStore(VectorStore):
    """Vector store adapter for Qdrant REST."""

    def ensure_collection(self, name: str, dim: int, distance: str = "Cosine", recreate: bool = False) -> None:
        timeout = http_timeout_seconds()
        base = qdrant_url()
        # Get collection
        with operation_timeout(timeout):
            r = requests.get(f"{base}/collections/{name}", timeout=timeout)
            if r.status_code == 404:
                r2 = requests.put(f"{base}/collections/{name}", json={"vectors": {"size": dim, "distance": distance}}, timeout=timeout)
                r2.raise_for_status()
                return
            r.raise_for_status()
            data = r.json()
        try:
            existing = int(data["result"]["config"]["params"]["vectors"]["size"])
        except Exception:
            existing = None
        if existing is not None and existing != dim:
            if not recreate:
                raise ValueError(f"Collection {name} has size={existing}, expected={dim}")
            with operation_timeout(timeout):
                dr = requests.delete(f"{base}/collections/{name}", timeout=timeout)
                dr.raise_for_status()
                cr = requests.put(f"{base}/collections/{name}", json={"vectors": {"size": dim, "distance": distance}}, timeout=timeout)
                cr.raise_for_status()

    def upsert_points(self, name: str, points: List[Point]) -> dict:
        timeout = http_timeout_seconds()
        base = qdrant_url()
        body = {
            "points": [
                {"id": p.id, "vector": p.vector.values, "payload": p.payload}
                for p in points
            ]
        }
        with operation_timeout(timeout):
            r = requests.put(f"{base}/collections/{name}/points?wait=true", json=body, timeout=timeout)
            r.raise_for_status()
            return r.json()

    def search(
        self,
        name: str,
        vector: Vector,
        limit: int = 5,
        with_payload: bool = True,
        score_threshold: Optional[float] = None,
    ) -> List[QueryResult]:
        timeout = http_timeout_seconds()
        base = qdrant_url()
        body = {
            "vector": vector.values,
            "limit": limit,
            "with_vector": False,
            "with_payload": with_payload,
        }
        if score_threshold is not None:
            body["score_threshold"] = float(score_threshold)

        # Optional thread-level payload filter to prevent cross-conversation bleed.
        # When a watcher lock exists, constrain search to meta.thread_id == THREAD_ID.
        tid = _load_thread_id_from_lock()
        if tid:
            body["filter"] = {"must": [{"key": "meta.thread_id", "match": {"value": tid}}]}

        with operation_timeout(timeout):
            r = requests.post(f"{base}/collections/{name}/points/search", json=body, timeout=timeout)
            r.raise_for_status()
            data = r.json() or {}
            return [
                QueryResult(
                    id=str(it.get("id")),
                    score=float(it.get("score", 0.0)),
                    payload=it.get("payload") or {},
                )
                for it in (data.get("result") or [])
            ]

    # --- Listing helpers for UI ---
    def list_collections(self) -> List[str]:
        """List collection names present in Qdrant."""
        timeout = http_timeout_seconds()
        base = qdrant_url()
        with operation_timeout(timeout):
            r = requests.get(f"{base}/collections", timeout=timeout)
            r.raise_for_status()
            data = r.json() or {}
        cols = []
        for it in (data.get("result", {}).get("collections", []) or []):
            name = str(it.get("name", "")).strip()
            if name:
                cols.append(name)
        return cols

    def get_collection_dim(self, name: str) -> Optional[int]:
        """Return the embedding dimension for a collection, if determinable."""
        timeout = http_timeout_seconds()
        base = qdrant_url()
        with operation_timeout(timeout):
            r = requests.get(f"{base}/collections/{name}", timeout=timeout)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json() or {}
        try:
            params = data["result"]["config"]["params"]["vectors"]
            # Single-vector config
            if isinstance(params, dict) and "size" in params:
                return int(params.get("size"))
            # Multi-vector config (map of name->config)
            if isinstance(params, dict):
                # Try first numeric size we find
                for v in params.values():
                    if isinstance(v, dict) and "size" in v:
                        sv = v.get("size")
                        with suppress(Exception):
                            return int(sv) if sv is not None else None
        except Exception:
            return None
        return None

    def list_collections_info(self) -> List[dict]:
        """Return list of {name, dim} for Qdrant collections."""
        names = self.list_collections()
        out: List[dict] = []
        for n in names:
            dim = None
            try:
                dim = self.get_collection_dim(n)
            except Exception:
                dim = None
            out.append({"name": n, "dim": dim})
        return out
