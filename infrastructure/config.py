from __future__ import annotations

import os


def env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def qdrant_url() -> str:
    return env_str("QDRANT_URL", "http://localhost:6333").rstrip("/")


def ollama_url() -> str:
    return env_str("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def embed_model() -> str:
    return env_str("EMBED_MODEL", "mxbai-embed-large")


def payload_text_max() -> int:
    try:
        return int(env_str("MEMORY_PAYLOAD_TEXT_MAX", "4096"))
    except Exception:
        return 4096


def chat_chunk_chars() -> int:
    """
    Chunk size for splitting chat messages into contiguous pieces before embedding.
    Defaults to 4000 when MEMORY_CHAT_CHUNK_CHARS is not set or invalid.
    """
    try:
        return int(env_str("MEMORY_CHAT_CHUNK_CHARS", "4000"))
    except Exception:
        return 4000
