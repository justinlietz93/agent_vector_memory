#!/usr/bin/env bash
# install-vector-memory.sh
# Global wrapper installer for vector-memory CLI without pip install.
# Makes the repo importable from anywhere by exporting PYTHONPATH to the repo root
# and installs simple launcher scripts into ~/.local/bin (or a provided prefix).
#
# Usage:
#   ./tools/install-vector-memory.sh
#   ./tools/install-vector-memory.sh --prefix /usr/local/bin
#
# After install, ensure the PREFIX is on your PATH, e.g.:
#   export PATH="$HOME/.local/bin:$PATH"
#
# Created by vector-memory setup

set -euo pipefail

prefix_default="${HOME}/.local/bin"
prefix="${prefix_default}"

# Resolve repo root (directory containing this script) -> repo root is two levels up if you keep tools/ at top-level.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
# Try to find repo root: prefer git if available, otherwise assume two levels up from tools/
if command -v git &>/dev/null; then
  if git -C "${script_dir}" rev-parse --show-toplevel &>/dev/null; then
    repo_root="$(git -C "${script_dir}" rev-parse --show-toplevel)"
  else
    repo_root="$(cd "${script_dir}/.." && pwd)"
  fi
else
  repo_root="$(cd "${script_dir}/.." && pwd)"
fi

usage() {
  cat << USAGE
Install global launchers for vector-memory without pip install.

Options:
  --prefix PATH   Installation directory for launchers (default: ${prefix_default})
  -h, --help      Show this help

Examples:
  ./tools/install-vector-memory.sh
  ./tools/install-vector-memory.sh --prefix /usr/local/bin
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      shift
      if [[ $# -eq 0 ]]; then
        echo "ERROR: --prefix requires a path" >&2
        exit 2
      fi
      prefix="$1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

# Validate python
if ! PY_BIN="$(command -v python3 || command -v python)"; then
  echo "ERROR: Python interpreter not found on PATH" >&2
  exit 127
fi

# No subdirectory check needed; package is at repo root

# Create prefix dir
mkdir -p "${prefix}"

# Absolute repo root (no symlinks) for stable PYTHONPATH
if command -v realpath &>/dev/null; then
  repo_root_abs="$(realpath "${repo_root}")"
else
  # Fallback: cd and pwd
  repo_root_abs="$(cd "${repo_root}" && pwd)"
fi

# Launcher: vector-memory
launcher_vm="${prefix}/vector-memory"
cat > "${launcher_vm}" <<'LAUNCH'
#!/usr/bin/env bash
set -euo pipefail
PY_BIN="$(command -v python3 || command -v python || true)"
if [[ -z "${PY_BIN}" ]]; then
  echo "ERROR: python not found" >&2
  exit 127
fi
# Inject repo root on PYTHONPATH (templated at install-time)
__REPO_ROOT__PLACEHOLDER__
export PYTHONPATH="${__REPO_ROOT__}:${PYTHONPATH:-}"
exec "${PY_BIN}" -m vector_memory.cli.main "$@"
LAUNCH

# Launcher: vector-memory-mcp (simple MCP query CLI shim)
launcher_mcp="${prefix}/vector-memory-mcp"
cat > "${launcher_mcp}" <<'LAUNCH'
#!/usr/bin/env bash
set -euo pipefail
PY_BIN="$(command -v python3 || command -v python || true)"
if [[ -z "${PY_BIN}" ]]; then
  echo "ERROR: python not found" >&2
  exit 127
fi
# Inject repo root on PYTHONPATH (templated at install-time)
__REPO_ROOT__PLACEHOLDER__
export PYTHONPATH="${__REPO_ROOT__}:${PYTHONPATH:-}"
# Inline Python to call MCP API vector_query for convenience
exec "${PY_BIN}" - "$@" <<'PYCODE'
import json, sys
from argparse import ArgumentParser
from vector_memory.mcp.api import vector_query

p = ArgumentParser(description="vector-memory MCP query")
p.add_argument("--collection", required=True)
p.add_argument("--q", required=True)
p.add_argument("--k", type=int, default=5)
p.add_argument("--with-payload", action="store_true", default=True)
p.add_argument("--score-threshold", type=float, default=None)
ns = p.parse_args()
print(json.dumps(vector_query(ns.collection, ns.q, ns.k, ns.with_payload, ns.score_threshold), indent=2))
PYCODE
LAUNCH

# Install repo root into launchers
# shellcheck disable=SC2016
sed -i.bak "s|__REPO_ROOT__PLACEHOLDER__|__REPO_ROOT__='${repo_root_abs}'|" "${launcher_vm}" "${launcher_mcp}" || true
# On macOS BSD sed, .bak files may remain; remove if created
rm -f "${launcher_vm}.bak" "${launcher_mcp}.bak" 2>/dev/null || true

# Make executables
chmod +x "${launcher_vm}" "${launcher_mcp}"

cat <<REPORT

Installed vector-memory launchers (no pip install required):

  ${launcher_vm}
  ${launcher_mcp}

Ensure the install prefix is on your PATH. If not, add:
  export PATH="${prefix}:\$PATH"

Sanity check:
  vector-memory --help
  vector-memory new-project
  vector-memory recall --q "smoke" --k 1 --with-payload

Note:
  - These launchers hard-point PYTHONPATH to: ${repo_root_abs}
  - If you move/rename the repo directory, re-run this installer to update launchers.
REPORT
