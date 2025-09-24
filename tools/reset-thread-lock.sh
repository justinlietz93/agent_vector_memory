#!/usr/bin/env bash
# Reset the pinned Roo Code conversation lock and optionally restart the watcher
# Placement: vector_memory/tools/reset-thread-lock.sh
#
# What it does:
# - Deletes the watcher's current thread lock (current_thread.lock)
# - Optionally stops the running watcher process (watch_real.pid)
# - Optionally restarts the watcher (when WATCH_AUTORESTART=1)
#
# Usage:
#   bash vector_memory/tools/reset-thread-lock.sh
#   WATCH_AUTORESTART=1 bash vector_memory/tools/reset-thread-lock.sh
#
# Notes:
# - The watcher reads the lock only at startup. If you only clear the lock,
#   the existing watcher will keep watching the old folder. Stop + restart to re-pin.

set -euo pipefail

TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="${LOCK_FILE:-"${TOOLS_DIR}/current_thread.lock"}"
PID_FILE="${PID_FILE:-"${TOOLS_DIR}/watch_real.pid"}"
LOG_FILE="${LOG_FILE:-"${TOOLS_DIR}/watch_real.log"}"

info() { printf 'INFO | %s\n' "$*"; }
warn() { printf 'WARN | %s\n' "$*"; }
err()  { printf 'ERROR | %s\n' "$*" >&2; }

stop_watcher_if_running() {
  if [[ -f "${PID_FILE}" ]]; then
    local pid
    pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      info "Stopping watcher | PID=${pid}"
      kill "${pid}" 2>/dev/null || true
      # Give it a moment to exit
      sleep 0.5
      if kill -0 "${pid}" 2>/dev/null; then
        warn "Watcher still running, sending SIGKILL"
        kill -9 "${pid}" 2>/dev/null || true
      fi
    else
      warn "PID file exists but watcher not running: ${PID_FILE}"
    fi
    rm -f "${PID_FILE}" 2>/dev/null || true
  else
    info "No PID file found; watcher may not be running"
  fi
}

clear_lock() {
  if [[ -f "${LOCK_FILE}" ]]; then
    info "Clearing lock: ${LOCK_FILE}"
    rm -f "${LOCK_FILE}" || true
  else
    info "No lock file to clear: ${LOCK_FILE}"
  fi
}

restart_watcher_if_requested() {
  if [[ "${WATCH_AUTORESTART:-0}" == "1" ]]; then
    info "Restarting watcher (will auto-select latest updated folder)"
    nohup bash "${TOOLS_DIR}/watch_roo_code.sh" --reset > "${LOG_FILE}" 2>&1 & echo $! > "${PID_FILE}"
    info "Started watcher | PID=$(cat "${PID_FILE}" 2>/dev/null || echo ?) | log=${LOG_FILE}"
  else
    info "Not restarting watcher (set WATCH_AUTORESTART=1 to auto-restart)"
    info "Manual restart: nohup bash ${TOOLS_DIR}/watch_roo_code.sh --reset > ${LOG_FILE} 2>&1 & echo $! > ${PID_FILE}"
  fi
}

stop_watcher_if_running
clear_lock
restart_watcher_if_requested

info "Done."
