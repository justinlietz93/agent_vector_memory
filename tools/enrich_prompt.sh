#!/usr/bin/env bash
# Enrich a prompt with top vector memory result as a <vector_memory> injection.
# Usage:
#   echo "Your prompt text" | bash vector_memory/tools/enrich_prompt.sh
#   K=3 bash vector_memory/tools/enrich_prompt.sh "Another prompt"
#
# Env:
# - MEMORY_COLLECTION_NAME (recommended): vector collection to query (falls back to CLI default policy)
# - K (optional): number of results to retrieve (default 1; we inject only the top-1 block)
# - QDRANT_URL / OLLAMA_URL / EMBED_MODEL: standard envs used by vector-memory CLI
# - VM_THREAD_FILTER (default 1): when enabled and a lock exists, constrain recall to that thread
# - VM_THREAD_LOCK_FILE / LOCK_FILE: path to current_thread.lock (default ./vector_memory/tools/current_thread.lock)
set -euo pipefail

K="${K:-1}"

# Read prompt from arg or stdin
if [[ $# -ge 1 ]]; then
  PROMPT="$*"
else
  PROMPT="$(cat -)"
fi
PROMPT="${PROMPT%$'\n'}"  # trim trailing newline

# Resolve python
PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
if [[ -z "${PY}" ]]; then
  echo "ERROR: python not found in PATH" >&2
  exit 1
fi

# Thread lock resolution: default to project-local watcher lock if present
if [[ -z "${VM_THREAD_LOCK_FILE:-}" && -z "${LOCK_FILE:-}" ]]; then
  # Default: ./vector_memory/tools/current_thread.lock relative to CWD
  DEFAULT_LOCK="./vector_memory/tools/current_thread.lock"
  if [[ -f "${DEFAULT_LOCK}" ]]; then
    export VM_THREAD_FILTER="${VM_THREAD_FILTER:-1}"
    export VM_THREAD_LOCK_FILE="${DEFAULT_LOCK}"
  fi
else
  # Honor provided LOCK_FILE or VM_THREAD_LOCK_FILE
  if [[ -n "${LOCK_FILE:-}" && -z "${VM_THREAD_LOCK_FILE:-}" ]]; then
    export VM_THREAD_LOCK_FILE="${LOCK_FILE}"
  fi
  export VM_THREAD_FILTER="${VM_THREAD_FILTER:-1}"
fi

# Build query command (inherits env: VM_THREAD_FILTER/VM_THREAD_LOCK_FILE)
CMD=( "${PY}" -m vector_memory.cli.main query --q "${PROMPT}" --k "${K}" --with-payload )
if [[ -n "${MEMORY_COLLECTION_NAME:-}" ]]; then
  CMD+=( --name "${MEMORY_COLLECTION_NAME}" )
fi

# Execute query; tolerate empty results
JSON="$("${CMD[@]}" 2>/dev/null || true)"

# Extract top result fields with jq (if available)
if ! command -v jq >/dev/null 2>&1; then
  # Fallback: emit original prompt only
  printf "%s\n" "${PROMPT}"
  exit 0
fi

HAS_RESULT="$(printf '%s' "${JSON}" | jq -r '((.result // []) | length) >= 1')"
if [[ "${HAS_RESULT}" != "true" ]]; then
  # No memory found; return original prompt
  printf "%s\n" "${PROMPT}"
  exit 0
fi

# Pull top-1 details
TOP_SCORE="$(printf '%s' "${JSON}" | jq -r '(.result // [])[0].score // empty')"
TOP_TEXT="$(printf '%s' "${JSON}" | jq -r '(.result // [])[0].payload.text_preview // empty')"
TOP_META="$(printf '%s' "${JSON}" | jq -r '(.result // [])[0].payload.meta // empty | @json')"

# Output: original prompt + <vector_memory> block
printf "%s\n\n" "${PROMPT}"
printf "<vector_memory>\n"
printf "  <relevance score=\"%s\"/>\n" "${TOP_SCORE:-}"
printf "  <item>\n"
# Indent the memory text safely (preserve linebreaks)
if [[ -n "${TOP_TEXT}" ]]; then
  # shellcheck disable=SC2001
  printf "%s\n" "${TOP_TEXT}" | sed 's/^/    /'
fi
printf "  </item>\n"
if [[ -n "${TOP_META}" && "${TOP_META}" != "null" ]]; then
  printf "  <meta>%s</meta>\n" "${TOP_META}"
fi
printf "</vector_memory>\n"
