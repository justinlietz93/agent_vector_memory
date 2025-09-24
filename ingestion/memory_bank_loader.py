from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from ..domain.models import MemoryItem


def load_memory_items(directory: Path) -> List[MemoryItem]:
    """Load .md files from memory-bank directory into MemoryItem list."""
    items: List[MemoryItem] = []
    for p in sorted(directory.glob("*.md")):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        stat = p.stat()
        meta: Dict[str, object] = {
            "source": str(p),
            "name": p.name,
            "modified": getattr(stat, "st_mtime", 0),
            "size_bytes": stat.st_size,
            "kind": "memory-bank",
        }
        items.append(MemoryItem(text=text, meta=meta))
    return items
