from __future__ import annotations

import contextlib
import os
import json
import requests
from datetime import timezone
from pathlib import Path
from typing import Any, Optional, Sequence, Dict, List
from datetime import datetime

from ..infrastructure.logging import get_logger
from ..infrastructure.ollama.client import OllamaEmbeddingService
from ..infrastructure.qdrant.client import QdrantVectorStore
from ..infrastructure.timeouts import http_timeout_seconds, operation_timeout
from ..infrastructure.config import qdrant_url, chat_chunk_chars
from ..ingestion.memory_bank_loader import load_memory_items
from ..domain.models import MemoryItem
from ..application.dto import EnsureCollectionRequest, UpsertMemoryRequest, QueryRequest
from ..application.use_cases.ensure_collection import EnsureCollectionUseCase
from ..application.use_cases.upsert_memory import UpsertMemoryUseCase
from ..application.use_cases.query_memory import QueryMemoryUseCase
from .parsers import build_parser

logger = get_logger("vector_memory.cli")


def _parse_dotenv(dotenv_path: Path) -> Dict[str, str]:
    """Parse a simple .env file (KEY=VALUE per line, '#' comments, quotes stripped)."""
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


def _resolve_collection_name(explicit: Optional[str]) -> str:
    """Resolve collection name from explicit arg or MEMORY_COLLECTION_NAME env/.env."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    name = _env_get("MEMORY_COLLECTION_NAME")
    if not name:
        raise ValueError("MEMORY_COLLECTION_NAME not set in environment or .env; set it or pass --name")
    return name


def _list_additional_collections() -> List[str]:
    """List configured additional collections from env/.env (MEMORY_COLLECTION_NAME_2+)."""
    out: List[str] = []
    merged: Dict[str, str] = {}
    merged.update(_parse_dotenv(Path(".env")))
    # Process env last to allow overriding
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
    uniq: List[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def _allowed_collections() -> List[str]:
    """Allowed collection names declared in env/.env:
    - Primary: MEMORY_COLLECTION_NAME
    - Additional: MEMORY_COLLECTION_NAME_2..N
    Returns a de-duplicated list preserving declaration order.
    """
    allowed: List[str] = []
    primary = _env_get("MEMORY_COLLECTION_NAME")
    if primary and primary not in allowed:
        allowed.append(primary)
    for n in _list_additional_collections():
        if n and n not in allowed:
            allowed.append(n)
    return allowed


def _list_qdrant_collections() -> List[str]:
    """Fetch currently available Qdrant collections for helpful error messages."""
    try:
        timeout = http_timeout_seconds()
        base = qdrant_url()
        with operation_timeout(timeout):
            return _fetch_collections(base, timeout)
    except Exception:
        return []

def _fetch_collections(base, timeout):
    """
    Fetches the list of collection names from the Qdrant server.

    Sends a GET request to the Qdrant collections endpoint and returns a sorted, de-duplicated list of collection names.

    Args:
        base: The base URL of the Qdrant server.
        timeout: Timeout in seconds for the HTTP request.

    Returns:
        List[str]: Sorted list of unique collection names.
    """
    r = requests.get(f"{base}/collections", timeout=timeout)
    r.raise_for_status()
    data = r.json() or {}
    cols = []
    for it in (data.get("result", {}).get("collections") or []):
        name = it.get("name")
        if isinstance(name, str) and name.strip():
            cols.append(name.strip())
    # de-dup + sort for stable output
    return sorted(set(cols))


def _write_file_if_missing(path: Path, content: str) -> bool:
    """Write the provided text to ``path`` only when no file is present.

    Args:
        path: Destination file path that should be created when missing.
        content: UTF-8 text content to persist in the new file.

    Returns:
        bool: ``True`` when the file is created, ``False`` when the file already exists.

    Raises:
        OSError: Propagated when the filesystem refuses to create parent directories
            or write file contents.

    Side Effects:
        Creates any missing parent directories and writes text content to disk.
    """

    if path.exists():
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


# Template content for project-level MCP shim
_SHIM_CONTENT = """#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from typing import Optional, Sequence
from vector_memory.mcp.api import (
    vector_create_collection,
    vector_index_memory_bank,
    vector_query,
    vector_delete,
)


def run(argv: Optional[Sequence[str]] = None) -> int:
    '''Parse CLI arguments and dispatch MCP vector memory commands.

    Args:
        argv: Optional collection of CLI arguments excluding the executable name.

    Returns:
        int: Process exit code where ``0`` indicates success and non-zero values
            describe error states surfaced by the underlying vector memory API.

    Side Effects:
        Emits JSON payloads to standard output for result reporting.

    Timeout & Retries:
        Delegates timeout behaviour to the underlying vector memory functions.
    '''
    ap = argparse.ArgumentParser(description="Project MCP shim for vector_memory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("ensure")
    e.add_argument("--collection", required=True)
    e.add_argument("--dim", type=int, default=None)
    e.add_argument("--distance", default="Cosine")
    e.add_argument("--recreate", action="store_true")

    i = sub.add_parser("index")
    i.add_argument("--collection", required=True)
    i.add_argument("--directory", default="memory-bank")
    i.add_argument("--idns", default="mem")
    i.add_argument("--max-items", type=int, default=None)

    q = sub.add_parser("query")
    q.add_argument("--collection", required=True)
    q.add_argument("--q", required=True)
    q.add_argument("--k", type=int, default=5)
    q.add_argument("--with-payload", action="store_true", default=True)
    q.add_argument("--score-threshold", type=float, default=None)

    d = sub.add_parser("delete")
    d.add_argument("--collection", required=True)
    d.add_argument("--ids", nargs="+", required=True)

    ns = ap.parse_args(list(argv or []))
    try:
        if ns.cmd == "ensure":
            print(json.dumps(vector_create_collection(ns.collection, ns.dim, ns.distance, ns.recreate), indent=2)); return 0
        if ns.cmd == "index":
            print(json.dumps(vector_index_memory_bank(ns.collection, ns.directory, ns.idns, ns.max_items), indent=2)); return 0
        if ns.cmd == "query":
            print(json.dumps(vector_query(ns.collection, ns.q, ns.k, ns.with_payload, ns.score_threshold), indent=2)); return 0
        if ns.cmd == "delete":
            print(json.dumps(vector_delete(ns.collection, ns.ids), indent=2)); return 0
        print(json.dumps({"status":"error","error":f"Unknown cmd: {ns.cmd}"})); return 2
    except Exception as ex:
        print(json.dumps({"status":"error","error":f"{type(ex).__name__}: {ex}"})); return 3


def _main_entry(argv: Optional[Sequence[str]] = None) -> int:
    '''Internal helper that bridges ``main`` to ``run`` for reuse in tests.'''

    return run(argv)


def main():
    '''Entrypoint for the generated MCP shim.

    Returns:
        int: Exit status propagated from ``run``.

    Side Effects:
        Reads arguments from ``sys.argv`` and exits via ``SystemExit`` upon completion.
    '''

    import sys

    return _main_entry(sys.argv[1:])

if __name__ == "__main__":
    raise SystemExit(main())
"""


def _generate_doc(primary_collection: str) -> str:
    """Generate VECTOR_MEMORY_MCP.md content describing env-based collection resolution and usage."""
    extra = _list_additional_collections()
    extras_line = ("\\n- " + "\\n- ".join(extra)) if extra else " (none configured)"
    return f"""# Vector Memory MCP Usage

This project initializes vector memory using environment-based collection resolution.

Collections
- Primary: {primary_collection}
- Additional:{extras_line}

Environment variables
- MEMORY_COLLECTION_NAME: required. Primary collection name.
- MEMORY_COLLECTION_NAME_2..N: optional additional collection names.
- QDRANT_URL (default http://localhost:6333)
- OLLAMA_URL (default http://localhost:11434)
- EMBED_MODEL (default mxbai-embed-large)

CLI
- Ensure/create (uses probed embedding dimension):
  vector-memory ensure-collection --name "$MEMORY_COLLECTION_NAME"
- Remember (defaults to primary collection when --name omitted):
  vector-memory remember --text "Atomic fact to remember"
- Recall (defaults to primary collection when --name omitted):
  vector-memory recall --q "question" --k 8 --with-payload

MCP shim (CLI)
- The file ./mcp_vector_memory.py exposes ensure, index, query, delete.
- Agents can call it with the same env-based collection policy.

Policy
- If MEMORY_COLLECTION_NAME is not set (env or .env), commands that need a collection will fail and instruct you to set it.
"""


def run(argv: Optional[Sequence[str]] = None) -> int:
    ap = build_parser()
    ns = ap.parse_args(list(argv or []))

    emb = OllamaEmbeddingService()
    store = QdrantVectorStore()

    try:
        return dispatch_commands(ns, emb, store)
    except Exception as ex:  # keep CLI concise and user-friendly
        print(json.dumps({"status": "error", "error": f"{type(ex).__name__}: {ex}"}))
        return 3


def dispatch_commands(ns, emb, store):
    """
    Dispatches CLI commands to the appropriate vector memory use case.

    Commands:
    - new-project: ensure primary collection from env/.env and scaffold MCP shim + docs in CWD
    - ensure-collection: explicit ensure by name
    - index-memory-bank, remember, recall, query: default to MEMORY_COLLECTION_NAME if --name omitted
    - store-turn: persist a single chat turn (user/assistant) with deterministic IDs and metadata
    """
    if ns.cmd == "new-project":
        return new_project(emb, store)

    if ns.cmd == "ensure-collection":
        return _extracted_from_dispatch_commands_15(ns, emb, store)
    if ns.cmd == "index-memory-bank":
        return index_memory(ns, emb, store)

    if ns.cmd == "remember":
        return remember_memory(ns, emb, store)

    if ns.cmd == "recall":
        return _recall(ns, emb, store)
    if ns.cmd == "query":
        return _execute_command(ns, emb, store)
    if ns.cmd == "store-turn":
        return store_turn(ns, emb, store)

    print(json.dumps({"status": "error", "error": f"Unknown command: {ns.cmd}"}))
    return 2


def _serialize_query_result(result: object) -> Dict[str, Any]:
    """Convert a query match into a JSON-serializable mapping.

    Args:
        result: Query match object returned by the vector store or provided by tests.

    Returns:
        Dict[str, Any]: Sanitized representation including id, score, text, and payload when supplied.

    Side Effects:
        None.

    Raises:
        ValueError: Never raised directly; any errors originate from ``vars`` or payload serialization.
    """

    try:
        raw_attrs = dict(vars(result))
    except TypeError:
        raw_attrs = {}

    data: Dict[str, Any] = {}
    if "id" in raw_attrs and raw_attrs["id"] is not None:
        data["id"] = raw_attrs["id"]
    if "score" in raw_attrs and raw_attrs["score"] is not None:
        data["score"] = float(raw_attrs["score"])

    payload = raw_attrs.get("payload")
    text_value = raw_attrs.get("text")
    if isinstance(payload, dict):
        data["payload"] = payload
        if text_value is None:
            text_value = payload.get("text") or payload.get("text_preview")
    elif payload is not None:
        data["payload"] = payload

    if text_value is not None:
        data["text"] = text_value

    return data


def _execute_command(ns, emb, store):
    """
    Executes a query command against the specified Qdrant collection.

    Checks if the collection exists, then performs a query using the provided parameters and prints the results.

    Args:
        ns: Namespace object containing command-line arguments.
        emb: Embedding service instance.
        store: Vector store instance.

    Returns:
        int: 0 on success, 2 if the collection does not exist.
    """
    collection = _resolve_collection_name(getattr(ns, "name", None))
    available = _list_qdrant_collections()
    if collection not in available:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Collection '{collection}' does not exist in Qdrant.",
                    "requested": collection,
                    "available_collections": available,
                },
                indent=2,
            )
        )
        return 2
    results = QueryMemoryUseCase(emb, store).execute(
        QueryRequest(
            collection=collection,
            query=str(ns.q),
            k=int(ns.k),
            with_payload=bool(ns.with_payload),
            score_threshold=(float(ns.score_threshold) if getattr(ns, "score_threshold", None) is not None else None),
        )
    )
    serialized = [_serialize_query_result(r) for r in results]
    print(json.dumps({"status": "ok", "collection": collection, "result": serialized}, indent=2))
    return 0


# TODO Rename this here and in `dispatch_commands`
def _recall(ns, emb, store):
    """
    Executes a recall command against the specified Qdrant collection.

    Checks if the collection exists, then performs a recall query using the provided parameters and prints the results.

    Args:
        ns: Namespace object containing command-line arguments.
        emb: Embedding service instance.
        store: Vector store instance.

    Returns:
        int: 0 on success, 2 if the collection does not exist.
    """
    collection = _resolve_collection_name(getattr(ns, "name", None))
    available = _list_qdrant_collections()
    if collection not in available:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Collection '{collection}' does not exist in Qdrant.",
                    "requested": collection,
                    "available_collections": available,
                },
                indent=2,
            )
        )
        return 2
    results = QueryMemoryUseCase(emb, store).execute(
        QueryRequest(
            collection=collection,
            query=str(ns.q),
            k=int(ns.k),
            with_payload=bool(ns.with_payload),
            score_threshold=(
                float(ns.score_threshold)
                if getattr(ns, "score_threshold", None) is not None
                else None
            ),
        )
    )
    serialized = [_serialize_query_result(r) for r in results]
    print(json.dumps({"status": "ok", "collection": collection, "result": serialized}, indent=2))
    return 0


# TODO Rename this here and in `dispatch_commands`
def _extracted_from_dispatch_commands_15(ns, emb, store):
    target = str(ns.name).strip()
    allowed = _allowed_collections()
    if target not in allowed:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Collection '{target}' is not declared in environment (.env). "
                             f"Add it as MEMORY_COLLECTION_NAME or MEMORY_COLLECTION_NAME_2..N before creation.",
                    "requested": target,
                    "allowed_env_collections": allowed,
                    "available_collections": _list_qdrant_collections(),
                },
                indent=2,
            )
        )
        return 2
    EnsureCollectionUseCase(emb, store).execute(
        EnsureCollectionRequest(collection=target, dim=ns.dim, distance=str(ns.distance), recreate=bool(ns.recreate))
    )
    print(json.dumps({"status": "ok", "collection": target}, indent=2))
    return 0


def index_memory(ns, emb, store):
    """
    Index memory-bank markdowns into the vector store.
    Falls back to MEMORY_COLLECTION_NAME when --name omitted.
    """
    collection = _resolve_collection_name(getattr(ns, "name", None))
    root = Path(ns.dir)
    items = load_memory_items(root)
    if ns.max_items:
        items = items[: int(ns.max_items)]
    logger.info("Index request | collection=%s | dir=%s | candidates=%d", collection, root, len(items))
    resp = UpsertMemoryUseCase(emb, store).execute(
        UpsertMemoryRequest(collection=collection, items=items, id_namespace=str(ns.idns))
    )
    logger.info("Index completed | collection=%s | indexed=%d", collection, len(items))
    print(json.dumps({"status": "ok", "collection": collection, "raw": resp.raw}, indent=2))
    return 0


def _chunk(text: str, size: int) -> List[str]:
    """Split ``text`` into contiguous chunks honoring a minimum width of one character.

    Args:
        text: Source string that should be segmented.
        size: Desired chunk width in characters. Non-positive values are coerced to ``1``.

    Returns:
        List[str]: Ordered list of text segments covering the full input.

    Side Effects:
        None.

    Raises:
        ValueError: Never raised explicitly; the function relies on Python slicing semantics.
    """

    step = max(1, size)
    return [text[i : i + step] for i in range(0, len(text), step)]


def store_turn(ns, emb, store) -> int:
    """
    Persist a single chat turn (user/assistant) into vector memory with deterministic IDs.

    Required args on ns:
      thread_id: str
      turn_index: int
      role: "user" | "assistant"
      text: str
    Optional:
      name (collection), model, tool_calls (JSON string), files (list[str]), idns (namespace), chunk_chars
    """
    collection = _resolve_collection_name(getattr(ns, "name", None))
    available = _list_qdrant_collections()
    if collection not in available:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Collection '{collection}' does not exist in Qdrant.",
                    "requested": collection,
                    "available_collections": available,
                },
                indent=2,
            )
        )
        return 2

    thread_id = str(ns.thread_id).strip()
    turn_index = int(ns.turn_index)
    role = str(ns.role).strip()
    text = str(ns.text)
    model = getattr(ns, "model", None)
    files = list(getattr(ns, "files", []) or [])
    idns = str(getattr(ns, "idns", "chat"))
    chunk_size = int(getattr(ns, "chunk_chars", 0) or 0) or chat_chunk_chars()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    message_id = f"{thread_id}:{turn_index}"

    # Parse tool_calls JSON if provided
    tool_calls = None
    raw_tool_calls = getattr(ns, "tool_calls", None)
    if raw_tool_calls:
        with contextlib.suppress(Exception):
            tool_calls = json.loads(raw_tool_calls)

    from ..domain.models import MemoryItem  # local import to avoid circulars at top

    chunks = _chunk(text, chunk_size)
    items: List[MemoryItem] = []
    for i, part in enumerate(chunks):
        meta = {
            "kind": "chat",
            "thread_id": thread_id,
            "turn_index": turn_index,
            "role": role,
            "ts": ts,
            "message_id": message_id,
            "chunk_index": i,
            "tool_calls": tool_calls,
            "files_touched": files,
            "model": model if role == "assistant" and model else None,
            "source": f"chat:{thread_id}:{turn_index}:{role}:{i}",
        }
        # Remove None values for compact payload
        meta = {k: v for k, v in meta.items() if v is not None}
        items.append(MemoryItem(text=part, meta=meta))

    resp = UpsertMemoryUseCase(emb, store).execute(
        UpsertMemoryRequest(collection=collection, items=items, id_namespace=idns)
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "collection": collection,
                "indexed_chunks": len(items),
                "message_id": message_id,
                "raw": resp.raw,
            },
            indent=2,
        )
    )
    return 0


def new_project(emb, store) -> int:
    """
    Initialize a new project:
    - Resolve MEMORY_COLLECTION_NAME from env/.env
    - Ensure Qdrant collection (dimension probed from embedding model)
    - Scaffold ./mcp_vector_memory.py and ./VECTOR_MEMORY_MCP.md if missing
    """
    name = _env_get("MEMORY_COLLECTION_NAME")
    if not name:
        print(json.dumps({"status": "error", "error": "MEMORY_COLLECTION_NAME is not set in environment or .env"}, indent=2))
        return 2

    dim = emb.get_dimension()
    EnsureCollectionUseCase(emb, store).execute(
        EnsureCollectionRequest(collection=name, dim=dim, distance="Cosine", recreate=False)
    )

    cwd = Path(".").resolve()
    shim_path = cwd / "mcp_vector_memory.py"
    doc_path = cwd / "VECTOR_MEMORY_MCP.md"
    created_shim = _write_file_if_missing(shim_path, _SHIM_CONTENT)
    created_doc = _write_file_if_missing(doc_path, _generate_doc(name))

    # best-effort chmod +x for shim
    with contextlib.suppress(Exception):
        if created_shim:
            mode = shim_path.stat().st_mode
            shim_path.chmod(mode | 0o111)
    print(
        json.dumps(
            {
                "status": "ok",
                "collection": name,
                "dimension": dim,
                "mcp_shim_created": created_shim,
                "doc_created": created_doc,
                "additional_collections": _list_additional_collections(),
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    import sys
    return run(sys.argv[1:])


def remember_memory(ns, emb, store):
    """
    Remember conversational facts by upserting arbitrary text lines as MemoryItem points.

    Accepts repeated --text arguments and/or a --file whose non-empty lines each become one memory.
    Tags are added into payload to allow later filtering/analysis. IDs are deterministic via --idns.
    """
    collection = _resolve_collection_name(getattr(ns, "name", None))

    texts: List[str] = []
    for t in (ns.text or []):
        t = str(t).strip()
        if t:
            texts.append(t)

    if getattr(ns, "file", None):
        p = Path(ns.file)
        if p.exists():
            for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line:
                    texts.append(line)

    if not texts:
        print(json.dumps({"status": "ok", "collection": collection, "result": {"indexed": 0}}))
        return 0

    tags = list(ns.tag or [])
    meta_common = {
        "kind": "conversational",
        "tags": tags,
        "source": "cli:remember",
    }

    items = [MemoryItem(text=t, meta=meta_common) for t in texts]
    resp = UpsertMemoryUseCase(emb, store).execute(
        UpsertMemoryRequest(collection=collection, items=items, id_namespace=str(ns.idns))
    )
    print(json.dumps({"status": "ok", "collection": collection, "indexed": len(items), "raw": resp.raw}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
