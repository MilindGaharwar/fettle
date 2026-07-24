#!/usr/bin/env bash
# Fettle launcher — resolves a Python >= 3.11 interpreter portably and runs
# the given script from this directory, forwarding stdin and arguments.
#
# Resolution order:
#   1. $FETTLE_PYTHON (explicit override)
#   2. python3 on PATH, if >= 3.11
#   3. python3.13 / 3.12 / 3.11 / 3.10 on PATH
#   4. `uv python find` (if uv is installed)
#   5. newest uv-managed cpython under ~/.local/share/uv/python
#
# A missing/too-old interpreter is a loud, readable error — never a silent pass.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$1"
shift || true

_ok() {  # is $1 a python >= 3.11?
    [ -n "$1" ] && [ -x "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

PYTHON="${FETTLE_PYTHON:-}"

if ! _ok "$PYTHON"; then
    PYTHON="$(command -v python3 || true)"
fi

if ! _ok "$PYTHON"; then
    for v in 3.13 3.12 3.11; do
        PYTHON="$(command -v "python$v" || true)"
        _ok "$PYTHON" && break
    done
fi

if ! _ok "$PYTHON" && command -v uv >/dev/null 2>&1; then
    PYTHON="$(uv python find 2>/dev/null || true)"
fi

if ! _ok "$PYTHON"; then
    PYTHON="$(ls -d "$HOME"/.local/share/uv/python/cpython-3.1[1-9]*/bin/python3 2>/dev/null | sort -V | tail -1 || true)"
fi

if ! _ok "$PYTHON"; then
    echo "fettle: no Python >= 3.11 found (tried FETTLE_PYTHON, python3, python3.11-3.13, uv). Set FETTLE_PYTHON." >&2
    exit 0  # hooks must not hard-fail the session over environment issues
fi

# Tool availability (ruff/semgrep) is reported by `fettle doctor` and the
# individual checks, which warn and skip when a tool is missing. Hooks must
# never trigger network installs — that was a per-invocation, unpinned
# `uv tool install` before v1.0.1 (audit D6).

exec "$PYTHON" "$SCRIPT_DIR/$TARGET" "$@"
