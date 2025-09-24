# Vector Memory Module — Declarative Architecture

This document specifies the architecture of the vector-memory module as it exists and is intended to remain. It describes the layers, contracts, policies, operational assumptions, and invariants that govern the system.

Overview

- Purpose: Provide standards-driven vector memory for conversational and project context using Ollama embeddings and Qdrant vector storage.
- Design: Hybrid-Clean layered architecture with strict boundaries, deterministic behavior, and small, focused files.
- External services:
  - Qdrant (default <http://localhost:6333>)
  - Ollama with mxbai-embed-large (default <http://localhost:11434>)

Layering and Boundaries

- Domain layer (pure types and ports)
  - Models and errors live in:
    - [domain/models.py](domain/models.py)
    - [domain/errors.py](domain/errors.py)
  - Ports (framework-agnostic interfaces) live in:
    - [domain/interfaces.py](domain/interfaces.py)
  - Properties:
    - No imports from application, infrastructure, CLI, or MCP.
    - Contains only value objects, simple dataclasses, and abstract ports.

- Application layer (use-cases and DTOs)
  - DTOs live in:
    - [application/dto.py](application/dto.py)
  - Use-cases live in:
    - [application/use_cases/ensure_collection.py](application/use_cases/ensure_collection.py)
    - [application/use_cases/upsert_memory.py](application/use_cases/upsert_memory.py)
    - [application/use_cases/query_memory.py](application/use_cases/query_memory.py)
  - Responsibilities:
    - Orchestrate domain ports.
    - Validate requests, enforce policies (deterministic IDs, payload trimming), and normalize responses.
    - Depend on domain ports only; no direct HTTP or framework usage.

- Infrastructure layer (adapters and policy)
  - Environment/config, logging, timeouts:
    - [infrastructure/config.py](infrastructure/config.py)
    - [infrastructure/logging.py](infrastructure/logging.py)
    - [infrastructure/timeouts.py](infrastructure/timeouts.py)
  - External adapters:
    - Ollama embedding adapter:
      - [infrastructure/ollama/client.py](infrastructure/ollama/client.py)
    - Qdrant vector store adapter:
      - [infrastructure/qdrant/client.py](infrastructure/qdrant/client.py)
  - Properties:
    - Implements domain ports via HTTP.
    - Encapsulates service-specific JSON and endpoints.
    - Provides fallback timeouts when central policy is unavailable.

- Ingestion (local sources)
  - Memory-bank loader:
    - [ingestion/memory_bank_loader.py](ingestion/memory_bank_loader.py)
  - Properties:
    - Converts .md files into domain MemoryItem with metadata.
    - No network access; deterministic loading.

- Interface layer (entrypoints)
  - CLI:
    - [cli/parsers.py](cli/parsers.py)
    - [cli/main.py](cli/main.py)
  - MCP-friendly API:
    - [mcp/api.py](mcp/api.py)
  - Properties:
    - Thin translation from boundary input to application DTOs.
    - Structured JSON output suitable for automation.

Data and Contracts

- Embedding
  - Embedding vectors are produced by the Ollama adapter using the configured model (default mxbai-embed-large).
  - The embedding dimension is probed at runtime to drive Qdrant collection vector size.
- Vector storage
  - Collection ensure:
    - Read by GET /collections/{name}; if absent, PUT /collections/{name} with vectors.size and distance (Cosine).
    - On size mismatch, behavior is configurable (recreate or error).
  - Upsert:
    - PUT /collections/{name}/points?wait=true with a PointsList body.
  - Search:
    - POST /collections/{name}/points/search with vector, limit, and optional score_threshold.
- Payload policy
  - Each point payload contains:
    - text_preview (trimmed to MEMORY_PAYLOAD_TEXT_MAX, default 4096)
    - text_len
    - meta (source path, filename, modified time, size_bytes, kind)
- Identifier policy
  - Deterministic UUIDv5 derived from a stable namespace and document content, ensuring idempotent upsert and consistency across runs.

Configuration (environment)

- QDRANT_URL (default <http://localhost:6333>)
- OLLAMA_URL (default <http://localhost:11434>)
- EMBED_MODEL (default mxbai-embed-large)
- MEMORY_PAYLOAD_TEXT_MAX (default 4096)
- VM_LOG_LEVEL (default INFO)

Timeouts and Error Handling

- All blocking HTTP operations are wrapped by operation_timeout from [infrastructure/timeouts.py](infrastructure/timeouts.py) and use request-level timeouts.
- Where available, central policy timeouts are honored; otherwise, conservative defaults are applied.
- Adapters surface provider-specific errors as typed exceptions from the domain errors module.

Logging and Observability

- A single logger factory from [infrastructure/logging.py](infrastructure/logging.py) governs emission.
- Boundary logs are concise and user-readable.
- When applicable, logs include context keys: provider, operation, stage (start|mid_stream|finalize), failure_class, fallback_used.

Performance and Limits

- File size limit: every source file is constrained to 500 LOC or less.
- Embedding calls are executed per-text in the current implementation for simplicity and strict determinism; batching can be introduced behind the port without changing application contracts.
- Search defaults to small k to bound latency; callers can raise k as needed.

Security and Subprocess Policy

- No shelling out; only HTTP requests to validated local services.
- No dynamic code execution.
- Environment resolution uses fixed keys; no untrusted interpolation into endpoints.

Testing Strategy

- Domain: value semantics and port contracts.
- Application: use-case orchestration with mocked ports and policy validation.
- Infrastructure: adapters with HTTP stubs asserting contract conformance for ensure, upsert, and search.
- CLI/MCP: argument parsing and end-to-end wiring smoke tests.

Operational Assumptions

- Qdrant and Ollama are reachable on their defaults unless overridden by environment.
- The Ollama model mxbai-embed-large is available locally.
- The hosting environment is Linux; no GPU dependency is required by this module (external services may use ROCm/CUDA).

Structure (authoritative)

- Package roots and modules:
  - [__init__.py](__init__.py)
  - Domain: [domain](domain/__init__.py)
  - Application: [application](application/__init__.py)
  - Infrastructure: [infrastructure](infrastructure/__init__.py)
  - Ingestion: [ingestion](ingestion/__init__.py)
  - CLI: [cli](cli/__init__.py)
  - MCP: [mcp](mcp/__init__.py)

Non-Goals

- No bespoke model management or provider SDK wrapping beyond thin HTTP adapters.
- No database other than Qdrant for vector storage.
- No business logic inside infrastructure or interface layers.

Acceptance Conditions (invariants)

- Collections are created with the probed vector size and Cosine distance.
- Upserts are idempotent via deterministic identifiers.
- Queries return results with payload containing preview and metadata.
- All layers adhere to inward dependencies only; no cross-layer leakage.
- All public modules and functions include professional docstrings describing purpose, parameters, returns, errors, side effects, and timeout policies.
