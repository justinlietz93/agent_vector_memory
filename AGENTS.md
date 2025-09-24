# Vector Memory — AGENTS.md (Usage Guide for AI Agents)

Purpose

- Define how an AI agent should create, update, and retrieve long-term memory using this module.
- Standardize memory hygiene, ingestion flow, and retrieval patterns to keep memories accurate, useful, and low-noise.

Authority

- This document is self-contained and authoritative for the vector-memory module.
- It describes CLI and MCP entrypoints for agents; it does not require external project documents.

Services and Defaults

- Qdrant: <http://localhost:6333>
- Ollama: <http://localhost:11434> (model: mxbai-embed-large)

Environment Variables

- MEMORY_COLLECTION_NAME (required) Primary collection name. Agents MUST pass this value to the CLI via --name.
  - Example: export MEMORY_COLLECTION_NAME=my_project_memory
- MEMORY_COLLECTION_NAME_2..N (optional) Additional collection names for specialized memory streams (e.g., secondary memory, policies).
  - Example:
    - export MEMORY_COLLECTION_NAME_2=my_secondary_memory
    - export MEMORY_COLLECTION_NAME_3=team_policies
- QDRANT_URL (default <http://localhost:6333>)
- OLLAMA_URL (default <http://localhost:11434>)
- EMBED_MODEL (default mxbai-embed-large)
- MEMORY_PAYLOAD_TEXT_MAX (default 4096)
- VM_LOG_LEVEL (default INFO)

Collections (Critical)

- Always pass --name explicitly to CLI commands.
- Agent-side resolution policy:
  - Prefer environment if set:
    - Primary: use $MEMORY_COLLECTION_NAME
    - Alternates: use $MEMORY_COLLECTION_NAME_2, $MEMORY_COLLECTION_NAME_3, ... as needed
  - If not set, prompt the user or abort; do NOT invent names.
- Recommended convention:
  - export MEMORY_COLLECTION_NAME=my_project_memory
  - export MEMORY_COLLECTION_NAME_2=my_secondary_memory
  - export MEMORY_COLLECTION_NAME_3=team_policies

Recommended Environment Setup

```bash
# Required primary collection
export MEMORY_COLLECTION_NAME=my_project_memory

# Optional additional collections
export MEMORY_COLLECTION_NAME_2=my_secondary_memory
export MEMORY_COLLECTION_NAME_3=team_policies

# Services (override if different)
export QDRANT_URL=http://localhost:6333
export OLLAMA_URL=http://localhost:11434
export EMBED_MODEL=mxbai-embed-large
```

Entrypoints (What to call)

- CLI (thin boundary for ops):
  - Ensure/create collection:
    - vector-memory ensure-collection --name "$MEMORY_COLLECTION_NAME"
  - Index the memory-bank directory:
    - vector-memory index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank --max-items 100
  - Query (retrieve facts):
    - vector-memory query --name "$MEMORY_COLLECTION_NAME" --q "what is the GPU and endpoints to assume?" --k 5 --with-payload

- MCP-friendly API (for agent tool wiring):
  - Module path: [mcp/api.py](mcp/api.py)
  - Exposed functions:
    - vector_create_collection(collection: str, dim: Optional[int] = None, distance: str = "Cosine", recreate: bool = False)
    - vector_index_memory_bank(collection: str, directory: str = "memory-bank", id_namespace: str = "mem", max_items: Optional[int] = None)
    - vector_query(collection: str, query: str, k: int = 5, with_payload: bool = True, score_threshold: Optional[float] = None)
    - vector_delete(collection: str)  // destructive; only use with explicit human approval

Memory Model (What to store)

- Store atomic, re-usable, project-relevant facts the agent should recall later, such as:
  - Persistent user preferences and operating constraints (hardware, endpoints, tools).
  - Non-sensitive decisions and policies that apply across tasks.
  - Invariants that should not drift without human confirmation.
- Do NOT store:
  - Secrets (tokens, credentials), personally identifying data, or volatile/ephemeral information.
  - Large raw logs; store curated summaries instead.

Recommended Ingestion Flow (Write memory)

1) Append facts to markdown notes in memory-bank/ as short, clear bullets with context.
   Example file: memory-bank/agent_facts.md
   ---

   Title: Agent Operating Facts
   Updated: 2025-09-23
   ---

   - GPU: AMD 7900 XTX 24GB (ROCm)
   - Ollama: <http://localhost:11434> model=mxbai-embed-large
   - Qdrant: <http://localhost:6333>
   - Policy: Prefer precise, atomic facts; avoid secrets; summarize logs.
   - Practice: Re-index after writing new facts.

2) Re-index the memory-bank directory:
   - vector-memory index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank

3) Confirm idempotency
   - Upserts are deterministic via UUIDv5 on content+source; safe to re-index after incremental edits.

Retrieval Flow (Use memory)

- Targeted recall with a narrow question; keep queries concise and explicit.
- CLI:
  - vector-memory query --name "$MEMORY_COLLECTION_NAME" --q "Summarize persistent agent policies" --k 5 --with-payload
- MCP API:
  - vector_query(collection="my_project_memory", query="architecture guardrails for memory hygiene", k=5, with_payload=True, score_threshold=0.25)
    - Note: score_threshold is optional; use it to filter weak matches.

Quality and Hygiene (How to keep memory healthy)

- Granularity: Prefer many short, atomic facts vs. few long blobs.
- Brevity: Default max payload preview is 4096 chars; put only what you need for recall.
- De-duplication: Edit/merge existing bullets; then re-index. Idempotent IDs prevent duplicate points on unchanged content.
- Provenance: Keep each note’s first lines with a title and date for basic lineage.
- Periodic refresh: Re-index after any meaningful edits to memory-bank notes.

Bootstrap (First-time setup)

- Create the collection once per project:
  - vector-memory ensure-collection --name "$MEMORY_COLLECTION_NAME"
- If your orchestrator manages env resolution, ensure MEMORY_COLLECTION_NAME is set before calls.

Error Handling and Timeouts

- All network calls use request timeouts and operation_timeout internally.
- Failures surface as structured errors; retry only when the cause is transient (e.g., service not yet available).

Security and Privacy

- Never write tokens, passwords, or personal data to memory-bank or vector store.
- Only store public or low-risk, long-term useful information.
- When in doubt, prefer transient in-session memory (not persisted) or redact sensitive fragments.

Performance Notes

- Default k=5 for queries; increase only when needed to keep latency low.
- You may use score_threshold (MCP API) to filter low-quality matches.

Examples (End-to-end)

A) Add two new facts and re-index:

1) Append to memory-bank/agent_facts.md:
   - Embedding model: mxbai-embed-large via Ollama
   - Vector store: Qdrant REST PUT points (PointsList contract)
2) Index:
   - vector-memory index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank

B) Query for endpoints:

- vector-memory query --name "$MEMORY_COLLECTION_NAME" --q "What endpoints should I use for Qdrant and Ollama?" --k 5 --with-payload

C) MCP calls (pseudocode)

- vector_create_collection(collection="my_project_memory")
- vector_index_memory_bank(collection="my_project_memory", directory="memory-bank", id_namespace="mem", max_items=200)
- vector_query(collection="my_project_memory", query="persistent user preferences for environment", k=8, with_payload=True, score_threshold=0.3)

Operational Invariants

- Collection vector size matches probed embedding dimension.
- Upserts are idempotent via deterministic UUIDv5.
- Payloads include text_preview, text_len, meta (source path, filename, mtime, size, kind).

Where to Look in the Code

- CLI:
  - [cli/parsers.py](cli/parsers.py)
  - [cli/main.py](cli/main.py)
- MCP:
  - [mcp/api.py](mcp/api.py)
- Use-cases:
  - [application/use_cases/ensure_collection.py](application/use_cases/ensure_collection.py)
  - [application/use_cases/upsert_memory.py](application/use_cases/upsert_memory.py)
  - [application/use_cases/query_memory.py](application/use_cases/query_memory.py)

Checklist for Agents (before finishing a task)

- Are new persistent facts captured in memory-bank/*.md?
- Did you re-index the directory for those notes?
- Did you query for recall and include relevant facts in reasoning?
- Did you avoid recording secrets, PII, or volatile data?

This workflow keeps memory reliable, minimal, and actionable for future tasks.
