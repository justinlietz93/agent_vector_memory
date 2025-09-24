{
  "github.copilot.chat.codeGeneration.useInstructionFiles": true,
  "github.copilot.chat.codeGeneration.instructions": [
    {
      "text": "Architecture: modular monolith, strict layering, no provider bleed, no shims, files <= 500 LOC. Public APIs require full docstrings (purpose, params, returns, exceptions, side effects, timeout/retry). Add/adjust unit tests for each change (fast, isolated). Never print or commit secrets; use env vars. Prefer surgical edits over rewrites; keep diffs minimal and reversible. Use timeout helpers; log provider + operation context on exceptions. Subprocess: absolute binaries, fixed arg lists, shell=false; never interpolate user input. Dependencies flow inward; cross-layer via interfaces only."
    },
    {
      "text": "Vector Memory (Ollama + Qdrant): resolve endpoints from env. QDRANT_URL=http://localhost:6333, OLLAMA_URL=http://localhost:11434, EMBED_MODEL=mxbai-embed-large, MEMORY_COLLECTION_NAME=<primary> (required), MEMORY_COLLECTION_NAME_2..N=<optional>. Ensure collection: python -m vector_memory.cli.main ensure-collection --name \"$MEMORY_COLLECTION_NAME\". Index: python -m vector_memory.cli.main index-memory-bank --name \"$MEMORY_COLLECTION_NAME\" --dir memory-bank --idns \"mem\". Query before coding: python -m vector_memory.cli.main query --name \"$MEMORY_COLLECTION_NAME\" --q \"What prior decisions affect <TASK>?\" --k 8 --with-payload. Store only concise, reusable facts in memory-bank/*.md; no secrets/PII/chat logs; then re-index."
    },
    {
      "text": "Workflow: (1) Recall constraints via vector memory (query as above). (2) Plan minimal layered changes honoring ARCHITECTURE_RULES.md and recalled decisions. (3) Implement minimal edits; update/add unit tests. (4) Append stable decisions as bullets to memory-bank/activeContext.md or memory-bank/decisionLog.md; re-index."
    },
    {
      "file": ".github/copilot-instructions.md"
    }
  ],
  "github.copilot.chat.testGeneration.instructions": [
    {
      "text": "Generate focused unit tests (fast, isolated). Cover happy path and edge cases; include brief comments stating what the test proves. Prefer fixtures/fakes over real I/O. No global state; deterministic outcomes."
    }
  ],
  "github.copilot.chat.commitMessageGeneration.instructions": [
    {
      "text": "Use Conventional Commits (feat, fix, docs, style, refactor, test, chore). Keep subject <= 72 chars. Body: what/why (reference rules or decisions recalled from vector memory); include breaking changes if any."
    }
  ],
  "github.copilot.chat.pullRequestDescriptionGeneration.instructions": [
    {
      "text": "Title: concise. Summary: what/why. Architecture: reference specific rules. Tests: coverage and edge cases. Memory: bullets added to memory-bank and re-indexed. Risks: rollback strategy."
    }
  ],
  "chat.promptFiles": true,
  "chat.promptFilesLocations": {
    ".github": true
  },
  "chat.instructionsFilesLocations": {
    ".github": true
  }
}
