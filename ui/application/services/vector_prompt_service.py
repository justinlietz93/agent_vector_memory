"""
Vector Prompt Service.

Business logic for vector memory query operations.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, Iterable
from pathlib import Path
import re
import os

from ..interfaces.vector_memory_service import IVectorMemoryService
from ..interfaces.logger import ILogger
from ...shared.dto import QueryRequest, QueryResponse, QueryResult


class VectorPromptService:
    """Service for handling vector prompt operations."""

    def __init__(self, memory_service: IVectorMemoryService, logger: ILogger):
        """Initialize service with dependencies."""
        self._memory_service = memory_service
        self._logger = logger

    def execute_query(self, request: QueryRequest) -> QueryResponse:
        """
        Execute vector memory query.

        Args:
            request: Query parameters

        Returns:
            Query results with metadata

        Raises:
            ValueError: If request is invalid
        """
        self._validate_request(request)
        self._logger.info(f"Executing query on collection '{request.collection}'")

        try:
            raw_results = self._memory_service.query_memory(
                request.collection, request.prompt, request.k
            )
            # Convert raw results then prioritize items that actually carry a
            # text preview in their payload. This improves UX by surfacing
            # recently inserted items (which include payloads) ahead of older
            # points that might be missing payload metadata.
            results = self._prioritize_results_with_text_preview(
                self._convert_results(raw_results)
            )
            response = QueryResponse(
                results=results,
                collection=request.collection,
                query=request.prompt,
                total_found=len(results)
            )

            self._logger.info(f"Query completed. Found {len(results)} results")
            return response

        except Exception as e:
            self._logger.error(f"Query failed: {e}")
            raise

    def create_collection(self, name: str) -> None:
        """Create a new vector memory collection if the backend supports it.

        Parameters:
            name: Collection name to create.

        Behavior:
            - If the underlying memory service exposes ``create_collection`` or
              ``ensure_collection``, this method delegates to it.
            - Otherwise, logs a note stating that explicit creation is not supported
              and collections may be created implicitly on first use.

        Raises:
            ValueError: If the name is empty or whitespace.
            Exception: Propagates any backend errors that occur during creation.
        """
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValueError("Collection name cannot be empty")

        if hasattr(self._memory_service, "create_collection"):
            self._logger.info(f"Creating collection '{cleaned}' via backend API")
            result = getattr(self._memory_service, "create_collection")(cleaned)
            # Persist to .env
            self._append_collection_to_env(cleaned)
            return result
        if hasattr(self._memory_service, "ensure_collection"):
            self._logger.info(f"Ensuring collection '{cleaned}' exists via backend API")
            result = getattr(self._memory_service, "ensure_collection")(cleaned)
            # After backend operation succeeds, persist to .env
            self._append_collection_to_env(cleaned)
            return result

        # Fallback: no explicit API available
        self._logger.warning(
            "Backend does not support explicit collection creation; "
            "the collection may be created implicitly on first use.")
        # No exception here; UI will proceed with the chosen name
        # Still attempt to persist the chosen name to .env to track it.
        self._append_collection_to_env(cleaned)

    def _append_collection_to_env(self, name: str) -> str:
        """Append the next sequenced MEMORY_COLLECTION_NAME_* entry to the root .env.

        Parameters:
            name: The collection name to write as the new variable value.

        Returns:
            The variable name that was appended (e.g., ``MEMORY_COLLECTION_NAME_2`` or base name
            if none existed).

        Raises:
            OSError: If the .env file cannot be created or written.

        Notes:
            - If no existing MEMORY_COLLECTION_NAME entries are found, this writes the base
              ``MEMORY_COLLECTION_NAME="..."``.
            - Otherwise, it appends ``MEMORY_COLLECTION_NAME_N="..."`` where N is next index.
        """
        # Only allow .env writes from the GUI application context
        if os.environ.get("VM_UI_CONTEXT") != "1":
            self._logger.info("Skipping .env update: non-UI context")
            return ""

        env_path = self._find_env_file()
        env_path.parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
            except Exception as e:
                self._logger.warning(f"Failed reading .env ({env_path}): {e}")
                lines = []

        # Compute next index
        pattern = re.compile(r"^\s*MEMORY_COLLECTION_NAME(?:_(\d+))?=")
        max_idx = 0
        for ln in lines:
            m = pattern.match(ln)
            if not m:
                continue
            idx_s = m.group(1)
            idx = int(idx_s) if idx_s else 1
            if idx > max_idx:
                max_idx = idx

        next_idx = 1 if max_idx == 0 else max_idx + 1
        var_name = "MEMORY_COLLECTION_NAME" if next_idx == 1 else f"MEMORY_COLLECTION_NAME_{next_idx}"

        # Basic escaping of quotes
        value = name.replace('"', '\\"')
        new_line = f'{var_name}="{value}"'

        # Ensure file ends with newline, then append
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(new_line)

        # Write back
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._logger.info(f"Appended {var_name} to {env_path}")
        return var_name

    def _find_env_file(self) -> Path:
        """Locate the repository root .env file, creating path if missing.

        Strategy:
            - Walk ancestors from this file to find an existing .env.
            - If not found, prefer the ancestor containing ``pyproject.toml``.
            - Fallback to 4-levels-up from this file (repo root in this project).
        """
        here = Path(__file__).resolve()
        for anc in [here.parent] + list(here.parents):
            candidate = anc / ".env"
            if candidate.exists():
                return candidate
        for anc in [here.parent] + list(here.parents):
            if (anc / "pyproject.toml").exists():
                return anc / ".env"
        return here.parents[4] / ".env"

    def insert_data(self, collection: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Insert a single text item into the specified collection.

        Parameters:
            collection: Target collection name.
            text: Text content to insert.
            metadata: Optional metadata dictionary to store alongside the text.

        Raises:
            ValueError: If collection or text are empty.
            Exception: Propagates backend errors if insertion fails.
        """
        col = (collection or "").strip()
        if not col:
            raise ValueError("Collection name cannot be empty")
        txt = (text or "").strip()
        if not txt:
            raise ValueError("Text to insert cannot be empty")

        try:
            self._logger.info(f"Inserting data into collection '{col}'")
            # Prefer explicit API; adapter ensures collection exists
            if hasattr(self._memory_service, "insert_data"):
                meta = dict(metadata or {})
                tid = self._load_thread_id_from_lock()
                if tid and "thread_id" not in meta:
                    meta["thread_id"] = tid
                getattr(self._memory_service, "insert_data")(col, txt, meta, "ui")
            else:
                raise NotImplementedError("Backend does not support insert_data")
            self._logger.info("Insert completed successfully")
        except Exception as e:
            self._logger.error(f"Insert failed: {e}")
            raise

    def insert_many(self, collection: str, texts: Iterable[str], common_meta: Optional[Dict[str, Any]] = None) -> int:
        """Insert multiple text items into the specified collection.

        Parameters:
            collection: Target collection name.
            texts: Iterable of text strings to insert.
            common_meta: Optional metadata merged into each item.

        Returns:
            The number of items actually queued for insert (non-empty texts).
        """
        col = (collection or "").strip()
        if not col:
            raise ValueError("Collection name cannot be empty")
        items: List[Dict[str, Any]] = []
        base = dict(common_meta or {})
        tid = self._load_thread_id_from_lock()
        if tid and "thread_id" not in base:
            base["thread_id"] = tid
        for t in texts:
            s = (t or "").strip()
            if not s:
                continue
            items.append({"text": s, "meta": base.copy()})
        if not items:
            return 0
        try:
            self._logger.info(f"Inserting {len(items)} items into collection '{col}'")
            if hasattr(self._memory_service, "insert_many"):
                getattr(self._memory_service, "insert_many")(col, items, "ui")
            elif hasattr(self._memory_service, "insert_data"):
                for it in items:
                    getattr(self._memory_service, "insert_data")(col, it["text"], it.get("meta", {}), "ui")
            else:
                raise NotImplementedError("Backend does not support insert operations")
            self._logger.info("Bulk insert completed successfully")
            return len(items)
        except Exception as e:
            self._logger.error(f"Bulk insert failed: {e}")
            raise

    def insert_items(self, collection: str, items: List[Dict[str, Any]], id_namespace: str = "ui") -> int:
        """Insert multiple pre-shaped items with per-item metadata.

        Parameters:
            collection: Target collection name.
            items: List of dicts with shape {"text": str, "meta": Dict[str, Any]}.
            id_namespace: Logical namespace for deterministic IDs.

        Returns:
            The number of items attempted to insert (after empty-text filtering).

        Raises:
            ValueError: If collection is empty or items list is empty.
            Exception: On adapter/backend failures.
        """
        col = (collection or "").strip()
        if not col:
            raise ValueError("Collection name cannot be empty")
        filtered: List[Dict[str, Any]] = []
        tid = self._load_thread_id_from_lock()
        for it in items or []:
            t = str(it.get("text", "") or "").strip()
            if not t:
                continue
            meta = dict(it.get("meta", {}))
            if tid and "thread_id" not in meta:
                meta["thread_id"] = tid
            filtered.append({"text": t, "meta": meta})
        if not filtered:
            raise ValueError("No valid items to insert")
        try:
            self._logger.info(f"Inserting {len(filtered)} items into collection '{col}'")
            if hasattr(self._memory_service, "insert_many"):
                getattr(self._memory_service, "insert_many")(col, filtered, id_namespace)
            elif hasattr(self._memory_service, "insert_data"):
                for it in filtered:
                    getattr(self._memory_service, "insert_data")(col, it["text"], it.get("meta", {}), id_namespace)
            else:
                raise NotImplementedError("Backend does not support insert operations")
            self._logger.info("Bulk item insert completed successfully")
            return len(filtered)
        except Exception as e:
            self._logger.error(f"Bulk item insert failed: {e}")
            raise

    def _validate_request(self, request: QueryRequest) -> None:
        """Validate query request parameters."""
        if not request.collection.strip():
            raise ValueError("Collection name cannot be empty")
        if not request.prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if request.k < 1 or request.k > 50:
            raise ValueError("K must be between 1 and 50")

    def _convert_results(self, raw_results: List) -> List[QueryResult]:
        """Convert raw results to structured DTOs."""
        converted = []
        converted.extend(
            QueryResult(
                id=str(getattr(result, 'id', '')),
                score=float(getattr(result, 'score', 0.0)),
                text_preview=self._extract_text_preview(result),
                metadata=getattr(result, 'payload', {}) or {},
            )
            for result in raw_results
        )
        return converted

    def _prioritize_results_with_text_preview(self, results: List[QueryResult]) -> List[QueryResult]:
        """Reorder results so entries with non-empty ``text_preview`` come first.

        This keeps the original relative order within each group (stable sort)
        and ensures the UI's top-1 injected memory contains usable text when
        available. If all results lack previews, the original order is returned.

        Args:
            results: Converted list of ``QueryResult`` items in store-provided order.

        Returns:
            A list where items that have ``text_preview`` are placed before those
            without, preserving original ordering within each partition.
        """
        if not results:
            return results
        with_text = [r for r in results if (r.text_preview or "").strip()]
        without_text = [r for r in results if not (r.text_preview or "").strip()]
        if with_text and without_text:
            self._logger.debug(
                "Reordered results to prefer items with payload text_preview"
            )
        return with_text + without_text

    def _extract_text_preview(self, result) -> str:
        """Extract text preview from result."""
        payload = getattr(result, 'payload', {}) or {}
        return payload.get('text_preview', '') if isinstance(payload, dict) else ''

    # --- Collections listing ---
    def list_collections(self) -> List[Dict[str, Any]]:
        """List available collections with dimensions for UI selectors.

        Returns an empty list if the backend does not support enumeration or on error.
        """
        try:
            if hasattr(self._memory_service, "list_collections"):
                cols = getattr(self._memory_service, "list_collections")() or []
                # Normalize elements to dicts with name/dim keys
                out: List[Dict[str, Any]] = []
                for it in cols:
                    if isinstance(it, dict) and "name" in it:
                        out.append({"name": str(it.get("name", "")), "dim": it.get("dim")})
                    elif isinstance(it, str):
                        out.append({"name": it, "dim": None})
                return out
        except Exception as e:
            self._logger.warning(f"List collections failed: {e}")
        return []

    # --- thread id helper to align inserts with search filter ---
    def _load_thread_id_from_lock(self) -> Optional[str]:
        """Read THREAD_ID from the watcher lock file when filtering is enabled.

        Respects env controls similar to the Qdrant client:
        - VM_THREAD_FILTER: "1"/"true"/"yes" to enable (default). "0"/"false"/"no" to disable.
        - VM_THREAD_LOCK_FILE or LOCK_FILE: explicit path to the lock file.
        - Default path resolves to vector_memory/tools/current_thread.lock relative to this module.
        """
        enabled = str(os.getenv("VM_THREAD_FILTER", "1")).lower() in ("1", "true", "yes")
        if not enabled:
            return None
        # Resolve lock file
        lock_env = os.getenv("VM_THREAD_LOCK_FILE") or os.getenv("LOCK_FILE")
        if lock_env:
            p = Path(lock_env).expanduser()
        else:
            here = Path(__file__).resolve()
            # vector_memory/ui/application/services/vector_prompt_service.py -> vector_memory
            vm_root = here.parents[3]
            p = vm_root / "tools" / "current_thread.lock"
        if not p.exists():
            return None
        try:
            for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = (raw or "").strip()
                if not s or s.startswith("#") or "=" not in s:
                    continue
                k, v = s.split("=", 1)
                if k.strip() == "THREAD_ID":
                    tid = v.strip().strip('"').strip("'")
                    return tid if tid else None
        except Exception:
            return None
        return None
