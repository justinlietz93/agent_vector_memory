#!/usr/bin/env bash
# Pre-send injector for Roo Code prompts.
# Goal: Automatically append a <vector_memory> block to the last user prompt in the pinned conversation
#       BEFORE it is sent to the model API. Works alongside the watcher pin lock.
#
# How it works:
# - Reads the pinned thread from current_thread.lock (created by watch_roo_code.sh).
# - Watches THREAD_DIR/ui_messages.json for changes (close_write/create).
# - On each change, finds the most recent user message that has not been injected (vm_injected!=true),
#   queries vector memory for that prompt (thread-filtered), builds a <vector_memory> block,
#   and atomically writes the updated JSON back with the injection appended to .text and vm_injected=true.
#
# Binary/media guard:
# - Skips injection if the last user message contains binary/attachment fields likely to be images or large files:
#     .attachments[].contentType startswith("image/") OR .attachments[].type in ["image","file"]
#     OR (.files[] present) OR (.images[] present) OR (.toolInput[].image present)
# - Only injects for textual prompts to avoid mixing binary payloads.
#
# Requirements:
# - jq
# - python (for vector_memory CLI)
# - inotifywait (optional; polling fallback available)
#
# Env:
# - MEMORY_COLLECTION_NAME: target vector collection (required by CLI policy)
# - VM_THREAD_LOCK_FILE / LOCK_FILE: path to current_thread.lock (default ./vector_memory/tools/current_thread.lock)
# - VM_THREAD_FILTER (default 1): enable thread payload filter
# - LOG_LEVEL: INFO|DEBUG (default INFO)
# - LOG_FILE: optional log file; rotates when LOG_MAX_BYTES is exceeded
# - LOG_MAX_BYTES: rotate threshold in bytes (default 1048576)
#
# Start after the watcher is pinned:
#   nohup bash vector_memory/tools/pre_send_injector.sh > vector_memory/tools/injector.log 2>&1 & echo $! > vector_memory/tools/injector.pid
#
# Stop:
#   kill "$(cat vector_memory/tools/injector.pid)"
#
set -euo pipefail

LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Resolve lock file (shared with the watcher)
if [[ -n "${VM_THREAD_LOCK_FILE:-}" ]]; then
  LOCK_FILE="${VM_THREAD_LOCK_FILE}"
elif [[ -n "${LOCK_FILE:-}" ]]; then
  LOCK_FILE="${LOCK_FILE}"
else
  LOCK_FILE="$(cd "$(dirname "$0")" && pwd)/current_thread.lock"
fi

# Logging with optional rotation
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
    printf '%s\n' "${msg}" >&2
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
PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
if [[ -z "${PY}" ]]; then
  echo "ERROR: python not found in PATH" >&2
  exit 1
fi

# Load pinned thread from lock
if [[ ! -f "${LOCK_FILE}" ]]; then
  echo "ERROR: Lock file not found. Start the watcher first to pin a thread. (${LOCK_FILE})" >&2
  exit 2
fi
# shellcheck disable=SC1090
. "${LOCK_FILE}"
if [[ -z "${THREAD_DIR:-}" || ! -d "${THREAD_DIR}" ]]; then
  echo "ERROR: THREAD_DIR not set or missing in lock: ${LOCK_FILE}" >&2
  exit 2
fi
THREAD_ID="${THREAD_ID:-$(basename "${THREAD_DIR}")}"
UI_FILE="${THREAD_DIR}/ui_messages.json"

if [[ ! -f "${UI_FILE}" ]]; then
  log INFO "ui_messages.json not present yet at ${UI_FILE} — waiting for file creation"
fi

# inotify or polling
if command -v inotifywait >/dev/null 2>&1; then
  MODE="inotify"
else
  MODE="poll"
  log INFO "inotifywait not found; falling back to polling"
fi

# Build <vector_memory> block for a given prompt (top-1)
# Uses the vector_memory CLI (thread filter enabled via env).
query_block_for_prompt() {
  local prompt="$1"
  # Default filter enabled unless explicitly disabled
  export VM_THREAD_FILTER="${VM_THREAD_FILTER:-1}"
  export VM_THREAD_LOCK_FILE="${LOCK_FILE}"

  # Run the CLI query; extract top-1; render a <vector_memory> block
  local json
  if ! json="$("${PY}" -m vector_memory.cli.main query --q "${prompt}" --k 1 --with-payload 2>/dev/null)"; then
    echo ""
    return 0
  fi
  if ! command -v jq >/dev/null 2>&1; then
    echo ""
    return 0
  fi
  local has
  has="$(printf '%s' "${json}" | jq -r '((.result // []) | length) >= 1')"
  if [[ "${has}" != "true" ]]; then
    echo ""
    return 0
  fi
  local score text meta
  score="$(printf '%s' "${json}" | jq -r '(.result // [])[0].score // empty')"
  text="$(printf '%s' "${json}" | jq -r '(.result // [])[0].payload.text_preview // empty')"
  meta="$(printf '%s' "${json}" | jq -r '(.result // [])[0].payload.meta // empty | @json')"

  # Assemble block
  {
    printf "<vector_memory>\n"
    printf "  <relevance score=\"%s\"/>\n" "${score:-}"
    printf "  <item>\n"
    if [[ -n "${text}" ]]; then
      printf "%s\n" "${text}" | sed 's/^/    /'
    fi
    printf "  </item>\n"
    if [[ -n "${meta}" && "${meta}" != "null" ]]; then
      printf "  <meta>%s</meta>\n" "${meta}"
    fi
    printf "</vector_memory>"
  }
}

# Append block to the most recent Roo Code "ask" message not yet injected
inject_into_ui_messages() {
  local file="$1"
  if [[ ! -f "${file}" ]]; then
    return 0
  fi

  # Find the most recent Roo Code "ask" message that hasn't been injected yet
  # Roo Code format: [{"type":"ask","ask":"command","text":"user message"}, ...]
  local finder='
    def find_last_ask_idx(arr):
        [range(0; arr|length) | select(
            (arr[.].type // "") == "ask" and
            (arr[.].vm_injected // false) != true
        )] as $indices
        | if ($indices|length) > 0 then ($indices|max) else -1 end;

    . as $root |
    if ($root|type) == "array" then
        find_last_ask_idx($root) as $idx |
        {
            idx: $idx,
            has: ($idx >= 0),
            msg: (if $idx >= 0 then $root[$idx] else {} end)
        }
    else
        {idx: -1, has: false, msg: {}}
    end'

  # Retry loop to tolerate transient writes/partial JSON
  local state
  local tries=0
  while true; do
    if state="$(jq -c "${finder}" "${file}" 2>/dev/null)"; then
      break
    fi
    tries=$((tries+1))
    if [[ "${tries}" -ge 6 ]]; then
      log DEBUG "jq parse failed for ${file} after retries"
      return 0
    fi
    sleep 0.05
  done

  local has idx prompt_text
  has="$(printf '%s' "${state}" | jq -r '.has // false')"
  idx="$(printf '%s' "${state}" | jq -r '.idx // -1')"
  prompt_text="$(printf '%s' "${state}" | jq -r '.msg.text // ""')"

  # Skip if no uninjected ask message found
  if [[ "${has}" != "true" || -z "${prompt_text}" ]]; then
    return 0
  fi

  # Skip command messages (ask:"command") - only inject text messages
  local ask_type
  ask_type="$(printf '%s' "${state}" | jq -r '.msg.ask // ""')"
  if [[ "${ask_type}" == "command" ]]; then
    log DEBUG "Skipping command message injection"
    return 0
  fi

  # Build vector block (thread-filtered)
  local block
  block="$(query_block_for_prompt "${prompt_text}")"
  if [[ -z "${block}" ]]; then
    log DEBUG "No block returned for prompt; skipping injection"
    return 0
  fi

  # Append block to text and set vm_injected=true; write atomically
  local tmp
  tmp="$(mktemp)"
  jq --argjson i "${idx}" --arg add "${block}" '
    .[$i].text = (.[$i].text + "\n\n" + $add)
    | .[$i].vm_injected = true
  ' "${file}" > "${tmp}" 2>/dev/null || { rm -f "${tmp}"; return 0; }

  mv -f "${tmp}" "${file}"
  log INFO "Injected vector_memory into Roo Code ask message | idx=${idx} | thread_id=${THREAD_ID}"
}

log INFO "Pre-send injector starting | THREAD_DIR=${THREAD_DIR} | THREAD_ID=${THREAD_ID} | LOCK_FILE=${LOCK_FILE}"
log INFO "UI file: ${UI_FILE}"
export VM_THREAD_FILTER="${VM_THREAD_FILTER:-1}"
export VM_THREAD_LOCK_FILE="${LOCK_FILE}"

if [[ "${MODE}" == "inotify" ]]; then
  # React on writes/creates of ui_messages.json only
  while true; do
    inotifywait -e close_write,create --format '%w%f' "${THREAD_DIR}" 2>/dev/null \
      | while read -r path; do
          case "${path}" in
            "${UI_FILE}")
              # Small delay to allow the writer to finish
              sleep 0.02
              inject_into_ui_messages "${UI_FILE}"
              ;;
            *)
              ;;
          esac
        done
  done
else
  # Polling mode
  declare -A LAST_M=()
  while true; do
    if [[ -f "${UI_FILE}" ]]; then
      mt="$(stat -c %Y "${UI_FILE}" 2>/dev/null || echo 0)"
      prev="${LAST_M[${UI_FILE}]:-0}"
      if [[ "${mt}" != "${prev}" ]]; then
        LAST_M["${UI_FILE}"]="${mt}"
        inject_into_ui_messages "${UI_FILE}"
      fi
    fi
    sleep 0.2
  done
fi
