# vector store agent memory

Standards-driven vector memory module (Ollama + Qdrant) refactored with Hybrid-Clean architecture. Provides:

- Python package: `vector_memory` (domain, application, infrastructure, ingestion, cli, mcp)
- CLI entrypoint: `vector-memory`
- MCP-friendly API: `vector_memory.mcp.api` (shim executable still at `memory-bank/mcp_vector_memory.py`)

Requirements

- Python 3.9+
- Qdrant running (default <http://localhost:6333>)
- Ollama running with `mxbai-embed-large` (default <http://localhost:11434>)

Install (interactive setup recommended)

Run the setup script for guided configuration (creates .env, installs launcher, etc.):

```bash
python setup.py
```

It asks about collections, URLs, chat tailing, and usage modes (MCP/UI/passive).

Manual no-pip (if skipping setup.py):

From the repo root, run the installer to create global launchers (defaults to ~/.local/bin):

```bash
chmod +x ./tools/install-vector-memory.sh
./tools/install-vector-memory.sh
```

Ensure the prefix is on your PATH (e.g., for default):
```bash
export PATH="$HOME/.local/bin:$PATH"
# Add to ~/.bashrc for persistence
```

Alternative: pip install (for editable dev or virtualenv)
- Development (editable):
  pip install -e .
- Regular:
  pip install .

Note: Ensure your PATH includes the user scripts directory, e.g.:

- Linux: export PATH="$HOME/.local/bin:$PATH"

CLI usage (after launcher install or pip)

- Ensure collection (dimension 1024 for mxbai-embed-large):
  vector-memory ensure-collection --name crux_memory --dim 1024
- Index memory-bank directory (sample 5 docs first, then scale):
  vector-memory index-memory-bank --name crux_memory --dir memory-bank --max-items 5
- Query:
  vector-memory query --name crux_memory --q "architecture rules" --k 3

See QUICKSTART.md for full no-pip setup, .env config, and project bootstrapping.

Environment variables

- QDRANT_URL (default <http://localhost:6333>)
- OLLAMA_URL (default <http://localhost:11434>)
- EMBED_MODEL (default mxbai-embed-large)
- MEMORY_PAYLOAD_TEXT_MAX (default 4096)
- VM_LOG_LEVEL (default INFO)

Programmatic usage (MCP-friendly)

- from vector_memory.mcp.api import vector_create_collection, vector_index_memory_bank, vector_query, vector_delete

Architecture

- See ARCHITECTURE.md for layering, ports, DTOs, and contracts.
