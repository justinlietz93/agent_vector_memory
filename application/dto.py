from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict
from ..domain.models import MemoryItem


@dataclass(frozen=True)
class EnsureCollectionRequest:
    collection: str
    dim: Optional[int] = None
    distance: str = "Cosine"
    recreate: bool = False


@dataclass(frozen=True)
class UpsertMemoryRequest:
    collection: str
    items: List[MemoryItem]
    id_namespace: str = "mem"


@dataclass(frozen=True)
class QueryRequest:
    collection: str
    query: str
    k: int = 5
    with_payload: bool = True
    score_threshold: Optional[float] = None


@dataclass(frozen=True)
class UpsertResponse:
    provider: str
    raw: Dict[str, object]
