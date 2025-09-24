#!/usr/bin/env bash
# Watch Roo Code task folders and persist messages to vector memory
# Placement: vector_memory/tools/watch_roo_code.sh
#
# Behavior:
# - Watches ~/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks (override via $ROO_TASKS_DIR)
# - On create/modify of ui_messages.json or api_conversation_history.json under tasks/<uuid>/,
#   re-imports all messages idempotently into vector memory using `vector-memory store-turn`
# - thread_id is the task folder UUID (basename of tasks/<uuid>)
# - Deterministic IDs: thread_id|turn_index|role|chunk_index ensures safe re-import across runs
#
# Requirements:
# - Python available (invokes CLI via: python -m vector_memory.cli.main ...)
# - jq
# - inotifywait (inotify-tools)
#
# Environment:
# - MEMORY_COLLECTION_NAME (recommended). If set, `--name` can be omitted (policy in CLI).
# - ROO_TASKS_DIR (optional) default: $HOME/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks
# - STORE_SETTINGS (optional) "all" = store full content; any other value = store truncated (redacted) text
# - LOG_LEVEL (optional) INFO|DEBUG (default INFO)
# - LOG_FILE (optional) path to append logs; when set, rotation is applied
# - LOG_MAX_BYTES (optional) rotate threshold in bytes when using LOG_FILE (default 1048576)
#
# Usage:
#   export MEMORY_COLLECTION_NAME=roo_project_mem
#   bash vector_memory/tools/watch_roo_code.sh
#
# Notes:
# - This script imports the entire file on each write event. Upserts are idempotent, so duplicates are avoided.
# - If you rotate tasks, this recursive watcher automatically picks up new task folders.

set -euo pipefail

LOG_LEVEL="${LOG_LEVEL:-INFO}"
ROO_TASKS_DIR="${ROO_TASKS_DIR:-"$HOME/.config/Code/User/globalStorage/rooveterinaryinc.roo-cline/tasks"}"
STORE_SETTINGS="${STORE_SETTINGS:-redacted}"

# Lock file: ensures we pin to a single conversation folder (thread) until reset
LOCK_FILE="${LOCK_FILE:-$(dirname "$0")/current_thread.lock}"

# --reset argument clears the lock so a new latest-updated thread is selected
if [[ "${1:-}" == "--reset" ]]; then
  rm -f "${LOCK_FILE}" 2>/dev/null || true
  printf 'INFO | Cleared thread lock: %s\n' "${LOCK_FILE}" >&2
fi

# Write lock (THREAD_DIR + THREAD_ID)
write_lock() {
  local tdir="$1"
  local tid
  tid="$(basename "${tdir}")"
  mkdir -p "$(dirname "${LOCK_FILE}")" 2>/dev/null || true
  {
    printf 'THREAD_DIR=%q\n' "${tdir}"
    printf 'THREAD_ID=%q\n' "${tid}"
    printf 'LOCKED_AT=%q\n' "$(date +%s)"
  } > "${LOCK_FILE}.tmp"
  mv -f "${LOCK_FILE}.tmp" "${LOCK_FILE}"
}

# Read lock if present and valid
read_lock() {
  if [[ -f "${LOCK_FILE}" ]]; then
    # shellcheck disable=SC1090
    . "${LOCK_FILE}"
    if [[ -n "${THREAD_DIR:-}" && -d "${THREAD_DIR}" ]]; then
      return 0
    fi
  fi
  return 1
}

# Choose latest-updated thread directory by mtime of target files (fallback to dir mtime)
choose_latest_thread_dir() {
  local latest_dir=""
  local latest_ts=-1
  local d ts

  # Iterate immediate children directories under ROO_TASKS_DIR
  while IFS= read -r -d '' d; do
    local ui="${d}/ui_messages.json"
    local api="${d}/api_conversation_history.json"
    local ts_ui=0 ts_api=0 ts_dir=0
    [[ -f "${ui}" ]] && ts_ui="$(stat -c %Y "${ui}" 2>/dev/null || echo 0)"
    [[ -f "${api}" ]] && ts_api="$(stat -c %Y "${api}" 2>/dev/null || echo 0)"
    ts_dir="$(stat -c %Y "${d}" 2>/dev/null || echo 0)"
    ts="${ts_ui}"
    [[ "${ts_api}" -gt "${ts}" ]] && ts="${ts_api}"
    [[ "${ts_dir}" -gt "${ts}" ]] && ts="${ts_dir}"
    if [[ "${ts}" -gt "${latest_ts}" ]]; then
      latest_ts="${ts}"
      latest_dir="${d}"
    fi
  done < <(find "${ROO_TASKS_DIR}" -mindepth 1 -maxdepth 1 -type d -print0)

  if [[ -z "${latest_dir}" ]]; then
    echo ""  # none found
  else
    printf '%s' "${latest_dir}"
  fi
}

# Resolve the pinned THREAD_DIR honoring overrides and lock
get_locked_thread_dir() {
  # If user pins explicitly via CHAT_TASK_DIR, honor it and write lock
  if [[ -n "${CHAT_TASK_DIR:-}" && -d "${CHAT_TASK_DIR}" ]]; then
    write_lock "${CHAT_TASK_DIR}"
    THREAD_DIR="${CHAT_TASK_DIR}"
    THREAD_ID="$(basename "${THREAD_DIR}")"
    return 0
  fi

  # If an existing valid lock exists, use it
  if read_lock; then
    return 0
  fi

  # Otherwise, select the latest-updated dir and write a lock
  local chosen
  chosen="$(choose_latest_thread_dir)"
  if [[ -z "${chosen}" ]]; then
    echo "ERROR: No task subfolders found under ${ROO_TASKS_DIR}" >&2
    exit 2
  fi
  write_lock "${chosen}"
  THREAD_DIR="${chosen}"
  THREAD_ID="$(basename "${THREAD_DIR}")"
  return 0
}

# Rotate if LOG_FILE exceeds LOG_MAX_BYTES (default 1MB)
rotate_if_needed() {
  local max="${LOG_MAX_BYTES:-1048576}"
  if [[ -n "${LOG_FILE:-}" && -f "${LOG_FILE}" ]]; then
    local size
    size="$(wc -c < "${LOG_FILE}" 2>/dev/null || echo 0)"
    if [[ "${size}" -gt "${max}" ]]; then
      mv -f "${LOG_FILE}" "${LOG_FILE}.1" 2>/dev/null || true
      : > "${LOG_FILE}"
    fi
  fi
}

log() {
  local level="$1"; shift
  if [[ "${LOG_LEVEL}" == "DEBUG" || "${level}" != "DEBUG" ]]; then
    local msg
    msg="$(printf '%s | %s\n' "${level}" "$*")"
    # stderr (interactive/log redirection)
    printf '%s\n' "${msg}" >&2
    # Optional file logging with rotation
    if [[ -n "${LOG_FILE:-}" ]]; then
      mkdir -p "$(dirname "${LOG_FILE}")" 2>/dev/null || true
      printf '%s\n' "${msg}" >> "${LOG_FILE}"
      rotate_if_needed
    fi
  fi
}

require_cmd() {
  local c="$1"
  if ! command -v "${c}" >/dev/null 2>&1; then
    echo "ERROR: required command not found: ${c}" >&2
    exit 1
  fi
}

require_cmd jq
# Optional inotifywait; fall back to polling if unavailable
if command -v inotifywait >/dev/null 2>&1; then
  WATCH_WITH="inotify"
else
  WATCH_WITH="poll"
  log INFO "inotifywait not found; falling back to polling mode"
fi
# Determine python executable
if command -v python >/dev/null 2>&1; then
  PY="python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "ERROR: neither python nor python3 found" >&2
  exit 1
fi

if [[ ! -d "${ROO_TASKS_DIR}" ]]; then
  echo "ERROR: tasks root not found: ${ROO_TASKS_DIR}" >&2
  exit 1
fi

# redact_or_pass TEXT -> outputs either full text (STORE_SETTINGS=all) or truncated redacted
redact_or_pass() {
  local txt="$1"
  if [[ "${STORE_SETTINGS}" == "all" ]]; then
    printf '%s' "${txt}"
  else
    # Truncate to ~800 chars and annotate as redacted
    # Avoid leaking very long payloads or secrets when not explicitly allowed.
    local truncated
    truncated="$(printf '%s' "${txt}" | head -c 800)"
    printf '%s' "${truncated}"
    if [[ ${#txt} -gt 800 ]]; then
      printf '... [redacted]'
    fi
  fi
}

# import_messages FILE
# Parses FILE as either { "messages": [...] } or a top-level array of messages.
# Emits store-turn calls for each entry: (index, role, text)
import_messages() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    log DEBUG "Skip missing file: ${file}"
    return 0
  fi

  local dir uuid
  dir="$(dirname "${file}")"
  uuid="$(basename "${dir}")"
  local stream
  if jq -e 'has("messages")' "${file}" >/dev/null 2>&1; then
    stream=".messages"
  else
    stream="."
  fi

  # Build TSV of: index \t role \t base64(text)
  # Use multiple fallbacks for text fields commonly seen across tools.
  # role fallback defaults to "user" when absent.
  local tsv
  if ! tsv="$(jq -r "${stream} | to_entries[] | [(.key|tostring), (.value.role // \"user\"), ((.value.text // .value.content // .value.message // \"\") | @base64)] | @tsv" "${file}")"; then
    log DEBUG "No parsable entries in: ${file}"
    return 0
  fi

  local IFS=$'\n'
  for line in ${tsv}; do
    # Split into three fields; text is base64 and may contain arbitrary content safely
    local idx role text_b64
    idx="$(printf '%s' "${line}" | awk -F'\t' '{print $1}')"
    role="$(printf '%s' "${line}" | awk -F'\t' '{print $2}')"
    text_b64="$(printf '%s' "${line}" | awk -F'\t' '{print $3}')"

    # Decode base64 text (handle empty safely)
    local raw_text=""
    if [[ -n "${text_b64}" && "${text_b64}" != "null" ]]; then
      # Suppress base64 warnings on empty
      raw_text="$(printf '%s' "${text_b64}" | base64 -d 2>/dev/null || true)"
    fi

    # Apply STORE_SETTINGS gating
    local final_text
    final_text="$(redact_or_pass "${raw_text}")"

    # Skip storing if text is empty and not allowed
    if [[ -z "${final_text}" ]]; then
      continue
    fi

    # Idempotent upsert via deterministic IDs inside vector-memory CLI
    # Rely on env MEMORY_COLLECTION_NAME for implicit collection selection if set.
    log DEBUG "Upserting turn | thread_id=${uuid} | turn_index=${idx} | role=${role}"
    "${PY}" -m vector_memory.cli.main store-turn \
      --thread-id "${uuid}" \
      --turn-index "${idx}" \
      --role "${role}" \
      --text "${final_text}" \
      >/dev/null 2>&1 || log DEBUG "store-turn failed (non-fatal) for ${uuid}#${idx}"
  done
}

# Initial import of current files for the locked thread directory only
initial_scan() {
  local tdir="$1"
  log INFO "Initial scan | thread_dir=${tdir}"
  while IFS= read -r -d '' f; do
    log DEBUG "Importing initial file: ${f}"
    import_messages "${f}"
  done < <(find "${tdir}" -maxdepth 1 -type f \( -name 'ui_messages.json' -o -name 'api_conversation_history.json' \) -print0)
}

watch_loop() {
  local tdir="$1"
  log INFO "Watching for changes | thread_dir=${tdir} | mode=${WATCH_WITH}"
  if [[ "${WATCH_WITH}" == "inotify" ]]; then
    inotifywait -m -e close_write,create --format '%w%f' \
      --include 'ui_messages.json|api_conversation_history.json' \
      "${tdir}" 2>/dev/null | while read -r path; do
        # Small delay to allow editors to flush full content
        sleep 0.05
        log DEBUG "Change detected: ${path}"
        import_messages "${path}"
      done
  else
    # Polling mode (no inotifywait available)
    declare -A LAST_MTIME=()
    while true; do
      while IFS= read -r -d '' f; do
        mt="$(stat -c %Y "$f" 2>/dev/null || echo 0)"
        key="$f"
        prev="${LAST_MTIME[$key]:-0}"
        if [[ "$mt" != "$prev" ]]; then
          LAST_MTIME["$key"]="$mt"
          log DEBUG "Poll detected change: $f"
          import_messages "$f"
        fi
      done < <(find "${tdir}" -maxdepth 1 -type f \( -name 'ui_messages.json' -o -name 'api_conversation_history.json' \) -print0)
      sleep 1
    done
  fi
}

log INFO "Vector Memory Roo watcher starting"
log INFO "Tasks root: ${ROO_TASKS_DIR}"
log INFO "STORE_SETTINGS=${STORE_SETTINGS}"
log INFO "Watch mode: ${WATCH_WITH}"
log INFO "Python: ${PY}"
if [[ -n "${MEMORY_COLLECTION_NAME:-}" ]]; then
  log INFO "Target collection: ${MEMORY_COLLECTION_NAME}"
else
  log INFO "Target collection: (implicit resolution in CLI; set MEMORY_COLLECTION_NAME for explicit selection)"
fi

# Resolve and lock to a single conversation folder
get_locked_thread_dir
log INFO "Pinned thread | THREAD_ID=${THREAD_ID} | THREAD_DIR=${THREAD_DIR} | LOCK_FILE=${LOCK_FILE}"

# If lock became stale (dir missing), auto-reselect latest
if [[ ! -d "${THREAD_DIR}" ]]; then
  log INFO "Locked thread dir missing; re-selecting latest"
  rm -f "${LOCK_FILE}" 2>/dev/null || true
  get_locked_thread_dir
  log INFO "Re-pinned thread | THREAD_ID=${THREAD_ID} | THREAD_DIR=${THREAD_DIR}"
fi

initial_scan "${THREAD_DIR}"
watch_loop "${THREAD_DIR}"
