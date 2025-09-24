You are Roo Code operating inside this repository. Follow these rules exactly and use the memory system on every task.

Core rules

- Modular monolith; strict layering; no provider bleed; no shims; ≤ 500 LOC/file.
- Public APIs must include full docstrings (purpose, params, returns, exceptions, side effects, timeout/retry).
- Add/adjust unit tests for each change; tests must be fast and isolated.
- Never print or commit secrets/tokens; use environment variables only.
- Prefer surgical edits over rewrites; keep diffs minimal and reversible.
- Use timeout helpers; log provider + operation context on exceptions.
- Subprocess: absolute binary path, fixed arg lists, shell=false; never interpolate user input.
- Dependencies flow inward only; cross-layer communication via defined interfaces.

Vector memory (Ollama + Qdrant)

- Env endpoints:
  - QDRANT_URL=<http://localhost:6333>
  - OLLAMA_URL=<http://localhost:11434>
  - EMBED_MODEL=mxbai-embed-large
  - MEMORY_COLLECTION_NAME=<primary> (required)
  - MEMORY_COLLECTION_NAME_2..N=<optional additional collections>
- Ensure collection (dimension probed automatically):
  python -m vector_memory.cli.main ensure-collection --name "$MEMORY_COLLECTION_NAME"
- Index memory-bank markdown:
  python -m vector_memory.cli.main index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank --idns "mem"
- Query memory before planning/coding:
  python -m vector_memory.cli.main query --name "$MEMORY_COLLECTION_NAME" --q "What prior decisions affect <TASK>?" --k 8 --with-payload

Collection switching (strict policy)

- Always target a collection explicitly via --name. Never assume defaults in command code.
- Preferred selection order:
  1) If the task references a specific collection, use that literal name with --name.
  2) Else, use $MEMORY_COLLECTION_NAME (primary).
  3) Else, use an additional declared collection ($MEMORY_COLLECTION_NAME_2..N) that matches the task category (e.g., experiments/docs).
- Do not silently create new collections. If a new collection is required, first run ensure-collection with the explicit name.
- Announce the selected collection at the start of a task (log/echo).
- Examples:
  export MEMORY_COLLECTION_NAME="roo_project_mem"
  export MEMORY_COLLECTION_NAME_2="roo_experiments_mem"
  export MEMORY_COLLECTION_NAME_3="roo_docs_mem"

  # Ensure an alternate collection before first use

  python -m vector_memory.cli.main ensure-collection --name "$MEMORY_COLLECTION_NAME_2"

  # Index into the experiments collection

  python -m vector_memory.cli.main index-memory-bank --name "$MEMORY_COLLECTION_NAME_2" --dir memory-bank --idns "mem"

  # Query the docs collection

  python -m vector_memory.cli.main query --name "$MEMORY_COLLECTION_NAME_3" --q "Summarize our doc authoring conventions" --k 8 --with-payload

  # Use a one-off explicit name (must ensure first)

  python -m vector_memory.cli.main ensure-collection --name "roo_tmp_mem"
  python -m vector_memory.cli.main query --name "roo_tmp_mem" --q "What constraints apply to <TOPIC>?" --k 5 --with-payload

When to write memory

- Only after deriving stable, reusable facts (architecture decisions, validated conventions, environment specifics).
- Append concise bullets to memory-bank/activeContext.md or memory-bank/decisionLog.md.
- Re-index after updates:
  python -m vector_memory.cli.main index-memory-bank --name "$MEMORY_COLLECTION_NAME" --dir memory-bank --idns "mem"
- Never store secrets/PII or large diffs.
- Persist Roo Code chat turns to vector memory on every message using:
  python -m vector_memory.cli.main store-turn --name "$MEMORY_COLLECTION_NAME" --thread-id "<thread>" --turn-index <n> --role user|assistant --text "<content>"

Task loop (enforced)

1) Recall constraints via memory:
   python -m vector_memory.cli.main query --name "$MEMORY_COLLECTION_NAME" --q "Summarize constraints for <TASK>" --k 8 --with-payload
2) Plan minimal, layered changes honoring ARCHITECTURE_RULES.md and recalled decisions.
3) Implement minimal edits; update/add unit tests; keep files ≤ 500 LOC.
4) Record new stable decisions as bullets; re-index memory.
5) Keep changes small and reversible.

Safety

- Validate endpoints and target collection before operations; run ensure-collection on the exact target name.
- On provider/contract errors, fix env/config and retry. Do not introduce transitional shims.
- Keep memory logically separated by collection; never mix concerns across collections without deliberate selection.
