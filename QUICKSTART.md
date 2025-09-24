# Vector Memory — Quick Start (No pip install)

This guide makes the `vector-memory` CLI executable from ANY directory on any Linux machine without installing a package. It installs tiny launchers into a bin directory (defaults to `~/.local/bin`) that point at this repo via `PYTHONPATH`.

Requirements:

- Python 3.9+ available on PATH
- Services:
  - Qdrant reachable (default <http://localhost:6333>)
  - Ollama reachable (default <http://localhost:11434>) with model `mxbai-embed-large` available
    - Optional: `ollama pull mxbai-embed-large`

Repo root used below is this directory (where this QUICKSTART.md lives).

---

## 1) Install global launchers (no pip)

Run the installer script (it writes two tiny launchers into a bin directory):

```bash
# From repo root
chmod +x ./tools/install-vector-memory.sh
./tools/install-vector-memory.sh
```

- Default install prefix: `~/.local/bin`
- To install elsewhere (e.g., /usr/local/bin), run:

  ```bash
  sudo ./tools/install-vector-memory.sh --prefix /usr/local/bin
  ```

Ensure the chosen prefix is on your PATH:

```bash
# If you used the default:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

What this does:

- Installs two launchers that import this repo via `PYTHONPATH`:
  - `vector-memory` — main CLI wrapper for [python.main()](vector_memory/cli/main.py:1)
  - `vector-memory-mcp` — convenience MCP query CLI calling [python.vector_query()](vector_memory/mcp/api.py:41)
- The launchers are hard-pointed to the absolute path of this repo; if you later move/rename this directory, just re-run the installer.

Sanity check:

```bash
vector-memory --help
```

---

## 2) Minimal configuration (.env)

Create a `.env` in your project directory where you plan to use the memory. Commands default to resolving the active collection from this file or your environment.

Example `.env`:

```dotenv
# Required: default collection name (used when --name is omitted)
MEMORY_COLLECTION_NAME=my_project_memory

# Optional: additional collections you can target explicitly
MEMORY_COLLECTION_NAME_2=my_secondary_memory
# MEMORY_COLLECTION_NAME_3=another_memory

# Endpoints (defaults shown)
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434

# Embedding model (must be available in Ollama)
EMBED_MODEL=mxbai-embed-large

# Optional logging/payload sizing
VM_LOG_LEVEL=INFO
MEMORY_PAYLOAD_TEXT_MAX=4096
```

Resolution order for collection:

1) `--name` argument if provided
2) `MEMORY_COLLECTION_NAME` from the environment
3) `MEMORY_COLLECTION_NAME` from `.env` in the current working directory

If none is set and `--name` is omitted, commands that require a collection will fail with a clear error.

---

## 3) Bootstrap a new project

From THE project directory that contains your `.env`:

```bash
vector-memory new-project
# or:
vector-memory --new-project
```

This will:

- Probe the embedding dimension via Ollama (model `mxbai-embed-large`)
- Ensure the Qdrant collection exists (creates if missing)
- Generate:
  - `./mcp_vector_memory.py` — project-level MCP CLI shim
  - `./VECTOR_MEMORY_MCP.md` — usage and env policy for agents

If you have multiple projects, run the same steps independently in each project root (each with its own `.env` and collection).

---

## 4) Use it (from anywhere)

Assuming `.env` is present in the current directory:

- Remember conversational facts (defaults to `MEMORY_COLLECTION_NAME` when `--name` omitted):

  ```bash
  vector-memory remember \
    --text "User prefers vector memory for conversational context" \
    --text "Use mxbai-embed-large via Ollama at http://localhost:11434"
  ```

- Recall relevant memories:

  ```bash
  vector-memory recall --q "What GPU and endpoints should I assume?" --k 8 --with-payload
  ```

- Index `.md` files from a directory:

  ```bash
  vector-memory index-memory-bank --dir memory-bank --max-items 100
  ```

- Generic direct query:

  ```bash
  vector-memory query --q "architecture rules" --k 5 --with-payload
  ```

- Target an additional configured collection:

  ```bash
  vector-memory recall --name "$MEMORY_COLLECTION_NAME_2" --q "questions for secondary memory" --k 5
  ```

---

## 5) Common issues

- Command not found:
  - Ensure your chosen install prefix is on PATH (e.g., `~/.local/bin`)
- Qdrant errors (404/400):
  - Run `vector-memory new-project` in your project directory (ensures collection exists)
  - Verify `QDRANT_URL` and service reachability
- Ollama errors:
  - Verify `OLLAMA_URL` and that `mxbai-embed-large` is available (`ollama pull mxbai-embed-large`)
- Moved repository after install:
  - Re-run `./tools/install-vector-memory.sh` to update the launchers’ hard-coded repo path

---

## 6) Uninstall

Remove the launchers and reload your shell:

```bash
rm -f ~/.local/bin/vector-memory ~/.local/bin/vector-memory-mcp
# If you used a different prefix, remove from that directory instead
```

---

## 7) Notes on behavior and payloads

- Deterministic IDs: UUIDv5 with `namespace|source|text` avoids duplicates across re-ingestion.
- Payload shape: each point has `payload.text_preview`, `payload.text_len`, `payload.meta` (e.g., `{kind:"conversational", tags:[...], source:"cli:remember"}`).
- Contracts (FYI):
  - Qdrant ensure: `PUT /collections/{name}`
  - Upsert: `PUT /collections/{name}/points?wait=true`
  - Search: `POST /collections/{name}/points/search`
- All CLI defaults map to the `.env`-driven collection unless overridden via `--name`.

You are now set to use vector-memory globally without a Python package install, with per-project `.env` collections and simple one-time launcher setup.
