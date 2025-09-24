# vector store agent memory

Standards-driven vector memory module (Ollama + Qdrant) refactored with Hybrid-Clean architecture. Provides:

- Python package: `vector_memory` (domain, application, infrastructure, ingestion, cli, mcp)
- CLI entrypoint: `vector-memory`
- MCP-friendly API: `vector_memory.mcp.api` (shim executable still at `memory-bank/mcp_vector_memory.py`)

Requirements

- Python 3.9+
- Qdrant running (default <http://localhost:6333>)
- Ollama running with `mxbai-embed-large` (default <http://localhost:11434>)

Install (user site, no sudo)

- Development (editable):
  pip install --user -e .
- Regular:
  pip install --user .

Note: Ensure your PATH includes the user scripts directory, e.g.:

- Linux: export PATH="$HOME/.local/bin:$PATH"

CLI usage

- Ensure collection (dimension 1024 for mxbai-embed-large):
  vector-memory ensure-collection --name crux_memory --dim 1024
- Index memory-bank directory (sample 5 docs first, then scale):
  vector-memory index-memory-bank --name crux_memory --dir memory-bank --max-items 5
- Query:
  vector-memory query --name crux_memory --q "architecture rules" --k 3

Environment variables

- QDRANT_URL (default <http://localhost:6333>)
- OLLAMA_URL (default <http://localhost:11434>)
- EMBED_MODEL (default mxbai-embed-large)
- MEMORY_PAYLOAD_TEXT_MAX (default 4096)
- VM_LOG_LEVEL (default INFO)

Programmatic usage (MCP-friendly)

- from vector_memory.mcp.api import vector_create_collection, vector_index_memory_bank, vector_query, vector_delete

Architecture

- See memory-bank/vector_memory/ARCHITECTURE.md for layering, ports, DTOs, and contracts.
