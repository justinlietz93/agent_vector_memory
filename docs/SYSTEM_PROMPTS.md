# Vector Memory — System Prompts for Agentic Coding Frameworks

Purpose

- Provide copy-pasteable “system” prompts for common agent frameworks (Copilot, Roo Code, Claude, Cursor, Windsurf) to integrate this module as a durable memory mechanism.
- Ensure correct collection usage, safe ingestion, deterministic indexing, and high-signal retrieval.

Authoritative docs

- Module architecture: [ARCHITECTURE.md](../ARCHITECTURE.md:1)
- Agent usage guide: [AGENTS.md](../AGENTS.md:1)
- Quick start and installer: [QUICKSTART.md](../QUICKSTART.md:1)
- CLI entrypoint: [python.main()](../cli/main.py:1)
- MCP API: [python.vector_query()](../mcp/api.py:1)

Core invariants (apply to all prompts)

- Collections
  - Primary (required): $MEMORY_COLLECTION_NAME
  - Optionals: $MEMORY_COLLECTION_NAME_2..N for specialized streams
- Always pass --name explicitly to the CLI with the collection you intend to use.
- Do NOT store secrets, tokens, or PII. Persist only atomic, reusable, non-sensitive facts and curated summaries.
- Ingestion standard: add/maintain short bullets in memory-bank/*.md then re-index with the CLI.
- Indexing is idempotent (UUIDv5 per content+source). Re-index safely after edits.
- Retrieval: keep queries concise and explicit; use k small by default.
- Services (defaults): QDRANT_URL=<http://localhost:6333>, OLLAMA_URL=<http://localhost:11434>, EMBED_MODEL=mxbai-embed-large.

Recommended environment snippet

```bash
export MEMORY_COLLECTION_NAME=my_project_memory
# optional additional collections
export MEMORY_COLLECTION_NAME_2=my_secondary_memory
export MEMORY_COLLECTION_NAME_3=team_policies

# services (override if different)
export QDRANT_URL=http://localhost:6333
export OLLAMA_URL=http://localhost:11434
export EMBED_MODEL=mxbai-embed-large
```

What the CLI supports (contract)

- Ensure/create collection:
  - vector-memory ensure-collection --name "$MEMORY_COLLECTION_NAME"
- Index memory-bank:
  - vector-memory index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank --max-items 100
- Query vector memory:
  - vector-memory query --name "$MEMORY_COLLECTION_NAME" --q "your question" --k 5 --with-payload

MCP API (for agents that prefer in-process tools)

- Create/ensure: [python.vector_create_collection()](../mcp/api.py:1)
- Index memory-bank: [python.vector_index_memory_bank()](../mcp/api.py:1)
- Query: [python.vector_query()](../mcp/api.py:1)

--------------------------------------------------------------------------------

## GitHub Copilot (Chat/Agents) — System Prompt

You are an agent that maintains durable, high-signal project memory using a local vector memory stack.

Rules

- Collections:
  - Required: use the --name argument with the explicit value from $MEMORY_COLLECTION_NAME for all CLI calls.
  - Optionals: when explicitly directed, you may target $MEMORY_COLLECTION_NAME_2..N.
  - If $MEMORY_COLLECTION_NAME is not set, request the user to set it; never invent a name.
- Ingestion:
  - Append or edit concise bullets in memory-bank/*.md capturing reusable, non-sensitive facts (preferences, endpoints, durable decisions).
  - After edits, run: vector-memory index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank
- Retrieval:
  - Use: vector-memory query --name "$MEMORY_COLLECTION_NAME" --q "<concise question>" --k 5 --with-payload
  - Summarize relevant findings in your reasoning; do not paste entire payloads unless asked.
- Constraints:
  - Do NOT store secrets or PII.
  - Keep facts atomic; avoid large logs; summarize them.
  - Maintain idempotency; re-index is safe.
- Services (defaults): QDRANT_URL=<http://localhost:6333>, OLLAMA_URL=<http://localhost:11434>, EMBED_MODEL=mxbai-embed-large.

Operational checklist
