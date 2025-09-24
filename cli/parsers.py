from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Vector memory (Ollama + Qdrant)")
    # Allow either a subcommand or a top-level --new-project flag
    ap.add_argument(
        "--new-project",
        action="store_true",
        help="Initialize project using MEMORY_COLLECTION_NAME from env/.env; creates collection and MCP shim/docs",
    )
    sub = ap.add_subparsers(dest="cmd", required=False)

    # Bootstrap a new project from environment/.env (creates collection, writes MCP files)
    sub.add_parser("new-project")

    # Manage collection
    ec = sub.add_parser("ensure-collection")
    ec.add_argument("--name", required=True)
    ec.add_argument("--dim", type=int, default=None)
    ec.add_argument("--distance", default="Cosine")
    ec.add_argument("--recreate", action="store_true")

    # Index markdown files from memory-bank directory
    ix = sub.add_parser("index-memory-bank")
    ix.add_argument("--name", required=False, help="Collection name; defaults to $MEMORY_COLLECTION_NAME")
    ix.add_argument("--dir", default="memory-bank")
    ix.add_argument("--idns", default="mem")
    ix.add_argument("--max-items", type=int, default=None)

    add_subparser(sub, "query")
    # Remember conversational facts (direct text or file lines)
    rm = sub.add_parser("remember")
    rm.add_argument("--name", required=False, help="Collection name; defaults to $MEMORY_COLLECTION_NAME")
    rm.add_argument("--text", action="append", default=[], help="A memory line to store; can repeat")
    rm.add_argument("--file", help="Path to a file; each non-empty line becomes a memory")
    rm.add_argument("--tag", action="append", default=[], help="Tag label to add to memory payload; can repeat")
    rm.add_argument("--idns", default="convo", help="ID namespace for deterministic UUIDv5")

    # Store a chat turn (user/assistant) with metadata and chunking
    st = sub.add_parser("store-turn")
    st.add_argument("--name", required=False, help="Collection name; defaults to $MEMORY_COLLECTION_NAME")
    st.add_argument("--thread-id", required=True, help="Stable conversation/thread identifier")
    st.add_argument("--turn-index", type=int, required=True, help="Monotonic turn index in this thread (0,1,2,...)")
    st.add_argument("--role", required=True, choices=["user", "assistant"], help="Message role")
    st.add_argument("--text", required=True, help="Full message text")
    st.add_argument("--model", required=False, help="Assistant model id (assistant turns)")
    st.add_argument("--tool-calls", required=False, help="JSON string with compact tool call summary")
    st.add_argument("--files", action="append", default=[], help="Relative file paths touched; can repeat")
    st.add_argument("--idns", default="chat", help="ID namespace for deterministic UUIDv5")
    st.add_argument("--chunk-chars", type=int, default=None, help="Override chunk size (defaults to env MEMORY_CHAT_CHUNK_CHARS or 4000)")

    rc = add_subparser(sub, "recall")
    rc.add_argument("--score-threshold", type=float, default=None)

    return ap

def add_subparser(sub, arg1):
    """
    Adds a query or recall subparser to the CLI argument parser.

    This function creates a subparser for querying an existing collection, adding
    arguments for collection name, query string, result count, and payload inclusion.

    Args:
        sub: The subparsers object from argparse.
        arg1: The name of the subcommand to add.

    Returns:
        argparse.ArgumentParser: The configured subparser.
    """
    # Query existing collection
    result = sub.add_parser(arg1)
    result.add_argument(
        "--name",
        required=False,
        help="Collection name; defaults to $MEMORY_COLLECTION_NAME",
    )
    result.add_argument("--q", required=True)
    result.add_argument("--k", type=int, default=5)
    result.add_argument("--with-payload", action="store_true", default=True)

    return result
