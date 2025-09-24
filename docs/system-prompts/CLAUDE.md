# Project Memory (Claude Code)

- You are operating inside this repository. Follow these rules exactly.
- Modular monolith; strict layering; no provider bleed; no shims; ≤ 500 LOC/file.
- Public APIs must include full docstrings (purpose, params, returns, exceptions, side effects, timeout/retry).
- Add/adjust unit tests for each change; keep tests fast and isolated.
- Never print or commit secrets/tokens; use environment variables.
- Prefer surgical edits over rewrites; keep diffs minimal and reversible.
- Use timeout helpers; log provider + operation context on exceptions.
- Subprocess: absolute binaries, fixed arg lists, shell=false; never interpolate user input.
- Dependencies flow inward; cross-layer communication via defined interfaces only.

## Vector Memory (Ollama + Qdrant)

- Endpoints (from env):
  - QDRANT_URL=<http://localhost:6333>
  - OLLAMA_URL=<http://localhost:11434>
  - EMBED_MODEL=mxbai-embed-large
  - MEMORY_COLLECTION_NAME=<primary> (required); MEMORY_COLLECTION_NAME_2..N=<optional additional>

- Ensure collection:
  - python -m vector_memory.cli.main ensure-collection --name "$MEMORY_COLLECTION_NAME"

- Index memory-bank:
  - python -m vector_memory.cli.main index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank --idns "mem"

- Query before coding:
  - python -m vector_memory.cli.main query --name "$MEMORY_COLLECTION_NAME" --q "What prior decisions affect <TASK>?" --k 8 --with-payload

- Store only concise, reusable facts in memory-bank/*.md (no secrets/PII/chat logs); then re-index.

## Workflow (strict)

1. Recall constraints with vector memory (query above).
2. Plan minimal layered changes honoring project rules and recalled decisions.
3. Implement minimal edits; update/add unit tests.
4. Append stable decisions as bullets to memory-bank/activeContext.md or memory-bank/decisionLog.md; re-index.

## Imports (project context)

- @ARCHITECTURE_RULES.md
- @AGENTS.md
- @memory-bank/activeContext.md
- @memory-bank/decisionLog.md

## Individual Preferences (optional; not committed)

- @~/.claude/my-project-instructions.md
