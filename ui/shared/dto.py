"""
Data Transfer Objects.

Immutable data structures for cross-layer communication.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Any


@dataclass(frozen=True)
class QueryRequest:
    """Request for vector memory query."""
    collection: str
    prompt: str
    k: int


@dataclass(frozen=True)
class QueryResult:
    """Single query result with metadata."""
    id: str
    score: float
    text_preview: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class QueryResponse:
    """Complete query response."""
    results: List[QueryResult]
    collection: str
    query: str
    total_found: int
